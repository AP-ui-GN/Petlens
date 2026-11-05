"""Small paw adapter and visible-only metrics for MMPose 1.3.2.

Only paw_delta is trainable. Original checkpoint tensor names are retained.
The other 15 output channels always use the unmodified frozen head path.
"""
import json

import numpy as np
import torch
from torch import nn
from mmengine.evaluator import BaseMetric
from mmpose.models.heads import RTMCCHead
from mmpose.registry import METRICS, MODELS


@MODELS.register_module()
class PreservedPawHead(RTMCCHead):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        assert self.out_channels == 17
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        self.paw_delta = nn.Conv2d(self.in_channels, 2, 7, padding=3)
        self._zero_delta()

    def _zero_delta(self):
        nn.init.zeros_(self.paw_delta.weight)
        nn.init.zeros_(self.paw_delta.bias)

    def init_weights(self):
        super().init_weights()
        self._zero_delta()

    def train(self, mode=True):
        super().train(False)  # Freeze dropout and all original head behavior too.
        self.paw_delta.train(mode)
        return self

    def _classify(self, maps):
        features = self.gau(self.mlp(torch.flatten(maps, 2)))
        return self.cls_x(features), self.cls_y(features)

    def forward(self, feats):
        features = feats[-1].detach()
        with torch.no_grad():
            maps = self.final_layer(features)
            original = self._classify(maps)
        indices = torch.tensor([13, 16], device=features.device)
        adapted_maps = maps.index_add(1, indices, self.paw_delta(features))
        adapted = self._classify(adapted_maps)
        # GAU mixes keypoint tokens, so freezing its weights alone is insufficient.
        return tuple(old.index_copy(1, indices, new.index_select(1, indices))
                     for old, new in zip(original, adapted))


@METRICS.register_module()
class ReviewedPawMetric(BaseMetric):
    default_prefix = 'paw'

    def __init__(self, ann_file, **kwargs):
        super().__init__(**kwargs)
        with open(ann_file) as stream:
            data = json.load(stream)
        self.annotations = {a['image_id']: a for a in data['annotations']}
        assert len(self.annotations) == len(data['annotations'])

    def process(self, data_batch, data_samples):
        for sample in data_samples:
            gt = np.asarray(self.annotations[int(sample['img_id'])]['keypoints']).reshape(17, 3)
            pred = np.asarray(sample['pred_instances']['keypoints'])
            assert pred.shape == (1, 17, 2)
            assert np.isfinite(pred).all(), 'Nonfinite predictions must fail evaluation.'
            errors = {str(k): float(np.linalg.norm(pred[0, k] - gt[k, :2]))
                      for k in (13, 16) if gt[k, 2] > 0}
            swapped = None
            if gt[13, 2] > 0 and gt[16, 2] > 0:
                direct = errors['13'] + errors['16']
                cross = np.linalg.norm(pred[0, 13] - gt[16, :2]) + np.linalg.norm(pred[0, 16] - gt[13, :2])
                swapped = bool(cross < direct)
            self.results.append(dict(errors=errors, swap=swapped))

    def compute_metrics(self, results):
        metrics = {}
        for name, keys in [('left', ('13',)), ('right', ('16',)), ('both', ('13', '16'))]:
            values = [r['errors'][k] for r in results for k in keys if k in r['errors']]
            assert values
            metrics.update({f'{name}/count': len(values),
                            f'{name}/mean_px': float(np.mean(values)),
                            f'{name}/median_px': float(np.median(values)),
                            f'{name}/p90_px': float(np.percentile(values, 90)),
                            f'{name}/within_10px': float(np.mean(np.asarray(values) <= 10)),
                            f'{name}/within_20px': float(np.mean(np.asarray(values) <= 20))})
        swaps = [r['swap'] for r in results if r['swap'] is not None]
        metrics['bilateral_frames'] = len(swaps)
        metrics['swap_closer_fraction'] = float(np.mean(swaps)) if swaps else 0.
        return metrics
