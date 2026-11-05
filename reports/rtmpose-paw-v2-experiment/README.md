# Latest status: original checkpoint verified

The original `.pth` is now downloaded and its strict CPU loading/preservation smoke passed. See [pretrained verification](cpu-preflight.json) and [updated provenance](checkpoint-provenance.json). SHA256: `896e3665d849ef7eb9b6ec0995955796cc9810f024fa0aa0bdc18acb0d68bf52`. No compatibility fixes were needed. The checkpoint blocker described in the historical preparation report below is resolved; GPU environment verification remains pending.

# PetLens V2 RTMPose-m AP-10K pilot — execution preparation

CPU preparation and a single forward/backward smoke test passed. **GPU fine-tuning
is not launched: the exact original trainable `.pth` is absent.** No model weights
or datasets were downloaded; only environment software was installed. No commits
or pushes were made.

## Model identity and environment

The saved inference manifest and deployment ZIP identify exactly
`rtmpose-m_simcc-ap10k_pt-aic-coco_210e-256x256-7a041aa1_20230206`.
The existing 54 MB ONNX matches SHA256
`1cfd1c86e0d9e5d5f95178bcd95ee9a4e8386a624cd3c57519f27ff58cac7f28`;
its ZIP hash and embedded ONNX also match provenance. The ZIP's `detail.json`
supplies the original `.pth` URL. Searches of `/workspaces`, `/tmp`, and the
user cache found no trainable checkpoint. No different model was substituted,
and no ONNX-to-PyTorch weight conversion was attempted.
See [checkpoint provenance](checkpoint-provenance.json).

Installed isolated environment: `tmp/rtmpose-paw-v2/.venv`, Python **3.10.16**,
CPU torch **2.1.0**, torchvision **0.16.0**, MMCV **2.1.0** with compiled CPU ops,
MMEngine **0.10.7**, MMDetection **3.2.0**, MMPose **1.3.2**, NumPy **1.26.4**.
The torch 2.1.0 CPU wheel matches the published MMCV build. `pip check` passes.
[Resolved lock and setup instructions](../../training/rtmpose_paw_v2/README.md)
reproduce the environment. The CUDA equivalent is prepared, not installed/tested.
Version bounds were checked against the official
[MMPose](https://github.com/open-mmlab/mmpose/blob/v1.3.2/mmpose/__init__.py)
and [MMDetection](https://github.com/open-mmlab/mmdetection/blob/v3.2.0/mmdet/__init__.py) source.

## Data and adapter

All original **79 targets / 42 frames** remain unchanged in the validated source.
All 46 referenced PNGs exist, decode at 1080×1920 and match recorded hashes.
AP-10K order is compatible: left hind channel **13**, right hind **16**.
Other channels stay unknown `[0,0,0]` with zero loss weight.

Derived COCO now uses existing RT-DETR **dog boxes**, joined by the exact video
and prediction hashes plus frame index. All retained boxes are in bounds and
contain the labeled paws; the [40-frame contact sheet](box-contact-sheet.jpg)
was visually inspected. These are detector boxes, not newly human-annotated boxes.
Frames **78 and 85** have multiple-dog ambiguity and no selected box; their
**3 targets** are excluded from derived data, never interpolated or invented.

| Derived split | Frames | Targets |
|---|---:|---:|
| Pilot training, 46–65 | 20 | 39 |
| Buffer excluded, 66–75 | 10 | 20 |
| Temporal diagnostic, 76–90 with missing boxes excluded | 10 | 17 |
| All reviewed frames with usable boxes, later refit only | 40 | 76 |

A single video cannot supply independent validation. The ~0.33 s buffer reduces
adjacency but does not remove shared dog/scene/gait correlation. Keep the final
iteration fixed; do not tune/select on the diagnostic. `dog02` remains excluded
from training and model selection. Another independently reviewed video is needed
for generalization claims; full-body labels are needed to measure full-body accuracy.

The implemented **75,266-parameter hind-paw residual adapter** freezes every
original parameter and normalization buffer. GAU mixes keypoints, so the other
15 logits explicitly use the original frozen head path. Unknown targets receive
no supervision. The trained checkpoint must retain the custom head code.

## Checks completed and exact remaining work

[CPU smoke evidence](cpu-random-smoke.json): one real annotated crop, one in-memory
optimizer step, finite loss and nonzero adapter gradients; zero adapter equals
the stock head; frozen weights/buffers unchanged; other 15 logits bitwise equal
after the update. **Random initialization was used solely for architecture checks;
this does not verify or produce a pretrained/fine-tuned model.** No checkpoint was saved.

[Initialization/data checks](cpu-random-initialization.json) pass for every training
and diagnostic sample, actual dataloaders/collation, target dimensions, masking,
metric construction and named head tensor shapes inspected from the original ONNX.
Synthetic metric checks confirm unknown points are ignored and all 17 diagnostic
targets count even with zero predicted confidence. Configuration parsing was fixed
for MMEngine environment substitution. Full `.pth` key/tensor compatibility is
still unverified because the file is absent.

Before GPU fine-tuning:

1. Supply the **exact original `.pth`** identified in the deployment metadata;
   set `PETLENS_AP10K_CHECKPOINT`. Then run checkpoint preflight (including its
   preservation smoke) to verify every pretrained tensor and record SHA256.
2. Provision one 8–16 GB CUDA GPU, install the prepared CUDA 11.8 dependency list
   in a separate environment, and verify CUDA/MMCV imports. No GPU is available here.
3. After those checks and training authorization, launch the prepared 100-step
   pilot: batch 4, 256×256, AdamW 1e-5, no augmentation/EMA/sweep/best selection.

The [execution/evaluation procedure](../../training/rtmpose_paw_v2/README.md)
provides commands. Compare original and final candidates with identical detector
boxes: per-paw/pooled pixel error, p90, fractions within 10/20 px, and swap
checks without confidence filtering. No full-body AP, gait or generalization
claim is justified by this pilot.
