"""CPU config/data checks and optional one-step smoke; never full training.

Random-initialization mode verifies architecture only, not pretrained weights.
A smoke optimizer update is kept in memory and is never saved as a checkpoint.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

import numpy as np
import torch
from mmengine.config import Config
from mmengine.logging import MMLogger
from mmengine.runner import Runner
from mmengine.utils import import_modules_from_strings
from mmpose.models.heads import RTMCCHead
from mmpose.registry import DATASETS, METRICS, MODELS
from mmpose.utils import register_all_modules
import mmpose

from training.rtmpose_paw_v2.prepare import OUT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-random-init', action='store_true')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--report-out', type=Path, help='Write new verification evidence here instead of replacing the recorded CPU report.')
    args = parser.parse_args()
    if args.allow_random_init:
        assert not os.environ.get('PETLENS_AP10K_CHECKPOINT'), 'Choose checkpoint verification OR explicitly random architecture smoke.'
        os.environ['PETLENS_ALLOW_RANDOM_INIT'] = '1'
    os.environ.setdefault('MMPOSE_ROOT', str(Path(mmpose.__file__).parent / '.mim'))
    torch.set_num_threads(2)
    MMLogger.get_instance('petlens-paw-cpu', log_level='ERROR')
    torch.manual_seed(20261104)
    np.random.seed(20261104)
    register_all_modules()
    cfg = Config.fromfile('training/rtmpose_paw_v2/pilot_config.py')
    import_modules_from_strings(**cfg.custom_imports)
    assert cfg.model.head.loss.use_target_weight
    assert cfg.model.head.out_channels == 17
    assert cfg.model.backbone.init_cfg is None
    assert cfg.train_cfg.max_iters == 100 and cfg.val_dataloader.dataset.ann_file != cfg.train_dataloader.dataset.ann_file
    model = MODELS.build(cfg.model).cpu()
    model.init_weights()
    architecture = json.loads((OUT / 'onnx-architecture.json').read_text())
    for name, shape in architecture['head_initializer_shapes'].items():
        assert list(model.state_dict()[name].shape) == shape, name
    checkpoint_sha = None
    if cfg.load_from:
        path = Path(cfg.load_from)
        checkpoint = torch.load(path, map_location='cpu')
        state = {k.removeprefix('module.'): v for k, v in checkpoint['state_dict'].items()}
        assert state['head.final_layer.weight'].shape == (17, 768, 7, 7)
        assert state['head.cls_x.weight'].shape == (512, 256)
        assert state['head.cls_y.weight'].shape == (512, 256)
        incompatible = model.load_state_dict(state, strict=False)
        assert set(incompatible.missing_keys) == {'head.paw_delta.weight', 'head.paw_delta.bias'}, incompatible
        assert not incompatible.unexpected_keys, incompatible
        assert all(torch.equal(model.state_dict()[k], v) for k, v in state.items())
        checkpoint_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        assert args.allow_random_init
    model.train()
    trainable = {k: p.numel() for k, p in model.named_parameters() if p.requires_grad}
    assert set(trainable) == {'head.paw_delta.weight', 'head.paw_delta.bias'}, trainable
    assert not model.head.paw_delta.weight.count_nonzero()
    assert not model.head.paw_delta.bias.count_nonzero()
    datasets = {}
    counts = {}
    unknown = [i for i in range(17) if i not in (13, 16)]
    for name, loader in [('train', cfg.train_dataloader), ('diagnostic', cfg.val_dataloader)]:
        dataset = DATASETS.build(loader.dataset)
        datasets[name] = dataset
        total = 0
        for index in range(len(dataset)):
            item = dataset[index]
            assert item['inputs'].shape == (3, 256, 256)
            sample = item['data_samples']
            assert sample.gt_instances.bboxes.shape == (1, 4)
            if name == 'train':
                weights = sample.gt_instance_labels.keypoint_weights
                assert not weights[..., unknown].count_nonzero()
                assert torch.equal(weights, torch.as_tensor(sample.gt_instances.keypoints_visible > 0, dtype=weights.dtype))
                total += int(weights.count_nonzero())
                assert sample.gt_instance_labels.keypoint_x_labels.shape == (1, 17, 512)
        counts[name] = dict(frames=len(dataset), supervised_targets=total if name == 'train' else None)
        # Build the actual dataloader/sampler and collate one batch too.
        batch = next(iter(Runner.build_dataloader(loader, seed=20261104)))
        assert len(batch['inputs']) == 4
    metric = METRICS.build(cfg.val_evaluator)
    expected_diagnostic_targets = 0
    for image_id, ann in metric.annotations.items():
        truth = np.asarray(ann['keypoints']).reshape(17, 3)
        predicted = truth[:, :2].copy()
        predicted[truth[:, 2] == 0] = 10000  # Unknown predictions are ignored.
        metric.process(None, [dict(img_id=image_id, pred_instances=dict(
            keypoints=predicted[None], keypoint_scores=np.zeros((1, 17))))])
        expected_diagnostic_targets += ann['num_keypoints']
    metrics = metric.compute_metrics(metric.results)
    assert metrics['both/count'] == expected_diagnostic_targets == 17
    assert metrics['both/mean_px'] == 0 and metrics['both/within_10px'] == 1
    result = dict(mode='random architecture only' if args.allow_random_init else 'exact checkpoint',
                  checkpoint_sha256=checkpoint_sha, trainable=trainable, datasets=counts,
                  python=sys.version, versions={k: importlib.metadata.version(k) for k in
                      ['torch', 'torchvision', 'mmcv', 'mmengine', 'mmpose', 'mmdet', 'numpy', 'opencv-python']},
                  device='cpu', cuda_available=torch.cuda.is_available(), full_training_run=False,
                  onnx_named_head_tensor_shapes_match=True,
                  metric_checks=dict(unknown_points_ignored=True, zero_confidence_targets_counted=17,
                                     exact_original_pixel_targets_score_zero_error=True))
    if args.smoke:
        # One real annotated sample; only the adapter receives a single update.
        frozen = {k: v.detach().clone() for k, v in model.state_dict().items() if not k.startswith('head.paw_delta.')}
        sample = datasets['train'][0]
        data = model.data_preprocessor(dict(inputs=[sample['inputs']], data_samples=[sample['data_samples']]), training=True)
        with torch.no_grad():
            feats = model.extract_feat(data['inputs'])
            expected = RTMCCHead.forward(model.head, feats)
            actual = model.head(feats)
        assert all(torch.equal(a, b) for a, b in zip(expected, actual)), 'Zero adapter must match stock head exactly.'
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-5, weight_decay=0.)
        optimizer.zero_grad()
        losses = model(data['inputs'], data['data_samples'], mode='loss')
        loss = losses['loss_kpt']
        assert loss.isfinite() and loss.requires_grad
        loss.backward()
        gradient = float(model.head.paw_delta.weight.grad.norm())
        assert gradient > 0
        assert all(p.grad is None for n, p in model.named_parameters() if not n.startswith('head.paw_delta.'))
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.)
        optimizer.step()
        assert model.head.paw_delta.weight.count_nonzero()
        assert all(torch.equal(model.state_dict()[k], v) for k, v in frozen.items()), 'Frozen weights/buffers changed.'
        with torch.no_grad():
            after = model.head(feats)
        assert all(torch.equal(a[:, unknown], b[:, unknown]) for a, b in zip(expected, after)), 'Protected logits changed.'
        assert any(not torch.equal(a[:, [13, 16]], b[:, [13, 16]]) for a, b in zip(expected, after)), 'Adapter update had no effect.'
        result['smoke'] = dict(optimizer_steps=1, loss=float(loss.detach()), adapter_gradient_norm=gradient,
                               zero_adapter_matches_stock_head=True, frozen_weights_and_buffers_unchanged=True,
                               protected_15_logits_bitwise_equal_after_update=True, checkpoint_saved=False)
    suffix = 'cpu-random-smoke.json' if args.smoke else 'cpu-random-initialization.json'
    out = OUT / (suffix if args.allow_random_init else 'cpu-preflight.json')
    if args.report_out is not None:
        out = args.report_out
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
