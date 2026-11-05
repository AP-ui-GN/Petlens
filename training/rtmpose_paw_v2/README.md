# RTMPose paw pilot: environment and execution

[Current results and blockers](../../reports/rtmpose-paw-v2-experiment/README.md).
No full training has run. The only optimizer step was an authorized CPU smoke
with random initialization, discarded without saving a checkpoint.

## Reproduce the CPU environment

Run from the PetLens root on Linux x86_64. `setup_cpu.sh` expects **uv 0.9.9**
(`UV_BIN` can select its path) and uses CPython **3.10.16**. It downloads software
packages, never model weights/data. Environment: `tmp/rtmpose-paw-v2/.venv`.
Application/inference dependencies are unchanged.

```bash
bash training/rtmpose_paw_v2/setup_cpu.sh
python -m training.rtmpose_paw_v2.prepare
bash training/rtmpose_paw_v2/run.sh smoke
```

`requirements-cpu.lock.txt` pins the resolved environment, including the exact
compiled MMCV wheel hash. `requirements-cpu.txt` records the direct dependencies.
Set `UV_PYTHON_INSTALL_DIR` if the default temporary interpreter directory is
unavailable. Preserve/recreate that interpreter along with the venv.

`prepare` verifies the original export/PNG/review hashes, reuses only saved
single-dog detections from the matching source run, and regenerates deterministic
splits and audit evidence. Missing or ambiguous boxes are excluded; original
annotations and coordinates remain untouched. Temporal diagnostic frames are
not independent validation. No dog02 data is added.

`run.sh smoke` builds the real model and both data pipelines, then performs
**one** CPU forward/backward/optimizer step in memory. It uses explicit random
initialization because no original `.pth` is present, and tests zero-adapter
baseline equality, unknown target masking, adapter gradients, frozen parameters
and buffers, and preservation of the other 15 logits. It never saves weights.
This is an architecture check, not a substitute pretrained model.

## Exact checkpoint and preflight

The original deployment ZIP identifies
[the original RTMPose-m AP-10K PyTorch checkpoint](https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/rtmpose-m_simcc-ap10k_pt-aic-coco_210e-256x256-7a041aa1_20230206.pth).
See `reports/rtmpose-paw-v2-experiment/checkpoint-provenance.json`. Neither the
existing ONNX nor its deployment ZIP includes that `.pth`. No model was downloaded.

Once that exact file is supplied:

```bash
export PETLENS_AP10K_CHECKPOINT=/absolute/path/to/rtmpose-m_simcc-ap10k_pt-aic-coco_210e-256x256-7a041aa1_20230206.pth
bash training/rtmpose_paw_v2/run.sh check
# One preservation smoke with the original checkpoint, before launch:
PILOT_PYTHON=tmp/rtmpose-paw-v2/.venv/bin/python
"$PILOT_PYTHON" -m training.rtmpose_paw_v2.preflight --smoke
```

Preflight permits only two new missing tensors (`head.paw_delta.weight/bias`)
when loading the original state dict, rejects all other missing/unexpected keys
or incompatible shapes, and verifies exact pretrained tensors. It prints and
records the checkpoint SHA256. Named ONNX head tensor shapes and actual 256×256
input/512-bin outputs already match the prepared architecture; complete `.pth`
compatibility is pending. The exported model used MMPose 1.1.0; this is why strict
key/tensor checks against the installed 1.3.2 implementation are required.

## GPU launch, only after authorization

On a separate Linux x86_64 GPU environment, use Python 3.10.16 and the same build
tools/NumPy bootstrap, then install `requirements-gpu.txt` with
`pip install --no-build-isolation -r training/rtmpose_paw_v2/requirements-gpu.txt`.
It selects torch/torchvision **2.1.0/0.16.0 CUDA 11.8** and MMCV **2.1.0** for
that ABI; all shared packages retain the CPU-tested versions. GPU dependencies
and driver compatibility have **not** been tested or downloaded here.

```bash
export PILOT_PYTHON=/absolute/path/to/gpu-env/bin/python
export PETLENS_AP10K_CHECKPOINT=/absolute/path/to/the-original-ap10k.pth
"$PILOT_PYTHON" -m pip check
"$PILOT_PYTHON" -c 'import torch, mmcv.ops; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))'
bash training/rtmpose_paw_v2/run.sh check
# After passing checkpoint/preservation checks and training authorization:
bash training/rtmpose_paw_v2/run.sh train
```

`run.sh` locates the installed MMPose configs/tools; no source checkout is needed.
Training fails closed without a supplied checkpoint and CUDA. Backbone pretrained
initialization downloads are disabled. The training entry point clears the
random-initialization escape hatch used only by smoke checks.

Pilot: seed **20261104**, **100 iterations**, batch **4**, 256×256, FP32,
AdamW **1e-5**, zero weight decay, gradient clip 1, no augmentation/EMA/LR scaling.
Train 20 frames/39 targets; diagnostic 10 frames/17 targets after box exclusions.
Only final iteration is retained; no sweep or best-checkpoint selection.

## Evaluation and artifacts

Carry `components.py`, the resolved config, environment lock, source hashes,
original weight SHA256 and derived split audit with the trained checkpoint.
Loading the candidate with a stock head discards the adapter. The other 15
outputs are protected only relative to the same preprocessing and input boxes.

For the exact original baseline, the custom head loads with its extra adapter
zero initialized. For the candidate, load its complete custom state dict.
After training/inference authorization, use installed MMPose `tools/test.py`
with the pilot config and each checkpoint, keeping `flip_test=False` and identical
boxes. `ReviewedPawMetric` scores every visible target without confidence gating:
left/right/pooled counts, mean/median/p90 source-pixel error, fractions within
10/20 px, and bilateral swap-closer fraction. Review paired errors and overlays;
do not report full-body AP or gait/generalization claims.

The model's GAU mixes keypoints. `PreservedPawHead` therefore sends the other
15 outputs through the original frozen branch while adapting hind channels
13/16 using a zero-initialized 75,266-parameter residual convolution. All
unlabeled slots have zero target weight. Full-body labels are not required for
this protected pilot, but are necessary to measure full-body accuracy.
