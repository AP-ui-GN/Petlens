"""Real CUDA kernels and model forward/backward; no optimizer step or training."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import torch
import torchvision
import mmcv
from mmcv.ops import nms
from mmengine.config import Config
from mmengine.utils import import_modules_from_strings
from mmpose.registry import DATASETS, MODELS
from mmpose.utils import register_all_modules

assert sys.version_info[:3] == (3, 10, 16)
assert platform.machine() == 'x86_64'
assert torch.__version__ == '2.1.0+cu118' and torchvision.__version__ == '0.16.0+cu118'
assert mmcv.__version__ == '2.1.0' and torch.version.cuda == '11.8'
assert torch.cuda.is_available(), 'CUDA unavailable: select a GPU runtime.'
name = torch.cuda.get_device_name(0)
assert 'T4' in name and torch.cuda.get_device_capability(0) == (7, 5), name
# Exercise compiled CUDA extension, not merely its Python import.
boxes = torch.tensor([[0., 0., 10., 10.], [1., 1., 9., 9.]], device='cuda')
_, keep = nms(boxes, torch.tensor([.9, .8], device='cuda'), .5)
assert keep.cpu().tolist() == [0]
register_all_modules()
cfg = Config.fromfile('training/rtmpose_paw_v2/pilot_config.py')
import_modules_from_strings(**cfg.custom_imports)
model = MODELS.build(cfg.model).cuda()
model.init_weights()
state = torch.load(os.environ['PETLENS_AP10K_CHECKPOINT'], map_location='cpu')['state_dict']
state = {k.removeprefix('module.'): v for k, v in state.items()}
missing = model.load_state_dict(state, strict=False)
assert set(missing.missing_keys) == {'head.paw_delta.weight', 'head.paw_delta.bias'} and not missing.unexpected_keys
model.train()
sample = DATASETS.build(cfg.train_dataloader.dataset)[0]
data = model.data_preprocessor(dict(inputs=[sample['inputs']], data_samples=[sample['data_samples']]), training=True)
loss = model(data['inputs'], data['data_samples'], mode='loss')['loss_kpt']
assert loss.isfinite()
loss.backward()
assert model.head.paw_delta.weight.grad.isfinite().all()
assert model.head.paw_delta.weight.grad.norm() > 0
assert all(p.grad is None for n, p in model.named_parameters() if not n.startswith('head.paw_delta.'))
torch.cuda.synchronize()
report = dict(python=sys.version, torch=torch.__version__, cuda=torch.version.cuda,
              mmcv=mmcv.__version__, gpu=name, capability=[7, 5],
              driver=subprocess.check_output(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'], text=True).strip(),
              cuda_nms=True, model_forward_backward=True, optimizer_steps=0,
              loss=float(loss.detach()), peak_allocated_bytes=torch.cuda.max_memory_allocated())
Path('outputs/cuda-preflight.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
