# PetLens model card

PetLens measures a walking clip. It does not diagnose pain, injury, or disease.

## What runs

| Pipeline | When | What it measures |
| --- | --- | --- |
| `coco-pose` | torch, transformers, and the weights load | A dog box, then 17 human COCO joints. This checkpoint has no AP-10K head and is not canine pose. |
| `opencv-motion` | pose cannot run, or pose throws | Frame-to-frame picture change only |

New results do not use the older human-pose pipeline name. Saved walks that
used it still validate.

**Dog detector.** `PekingU/rtdetr_r50vd_coco_o365` (`RTDetrForObjectDetection`).
The model card on Hugging Face lists Apache-2.0. The dog class id is read
from `config.id2label`. It is not hard-coded. A box is kept at
`DOG_DETECT_THRESHOLD` 0.3.

**Pose.** `usyd-community/vitpose-plus-base` (`VitPoseForPoseEstimation`).
The Transformers docs list dataset index 3 as an AP-10K backbone expert.
The checkpoint file has one keypoint head. `config.id2label` and
`config.edges` are the 17 COCO human joints. Index 4 is `R_Ear`. The
original ViTPose++ training config defines a separate AP-10K head, and that
head is not in this file. Passing dataset index 3 does not change the
channel order.

On one side-view frame, channel 0 sat on the nose and channel 4 sat on the
ear, next to the head, not at the base of the tail. The pipeline therefore
names these channels with the COCO schema. It does not call channel 4
`root_of_tail`. Stride length, which needs the neck and the base of the
tail, stays unmeasured.

The loaded file has one decoder. Its last convolution has 17 output
channels. `config.id2label` is Nose through R_Ankle. The backbone config
has six experts. Dataset index 3 only selects one of those experts.

## Side-view review

This is one clip, not a validation set. `scripts/check_pose_backend.py` on
that clip sampled 60 frames at 960×544 and printed `schema=coco-17`,
`dogFramesShare=1.0`, `multipleDogs=False`, and `personPresent=True`. The
right ear's median was 91.0 px from the nose and 352.6 px from the left hip.
Both ankles were below the hips.

The dog box stays on the dog. A person at the left edge is recorded as
present and is not returned as the dog. The nose tracks the snout as the
dog walks left. On the drawn frames the nose, eyes, and ears sit on the
head, the shoulders sit on the withers, and the elbows, wrists, knees, and
ankles sit on the legs. Left and right are not a dog's left and right: the
median left and right eyes were 11.1 px apart, and the ears were 5.4 px
apart. On some frames the rear-leg links cross, and both hips can land on
the same part of the rump. The tail in the picture has no landmark.

Do not rename a channel to force a nose-farther-than-eyes rule or a
nose-to-tail rule. This head has no neck and no base of the tail. Those
stride numbers stay unmeasured until a checkpoint with an AP-10K keypoint
head is checked on its own.

Both models run on the server. The browser only uploads the clip.

## What is not validated

- Pose quality on a labeled set of pet dogs. One side-view frame was compared with `config.id2label`. Channel 4 is the right ear (91.0 px from the nose, 352.6 px from the left hip on that frame). That is a naming check, not a validation set.
- Left versus right on a side view. `left_knee` on that frame scored 0.38.
- Stride length from this head. It has no neck and no base of the tail, so those numbers stay unmeasured.
- Stride symmetry as a clinical measure
- Any link between a score and pain, injury, or disease

The canine-pose development audit, dataset source review, preparation command,
and acceptance gates are in [`docs/model_audit.md`](model_audit.md). The
official AP-10K split 1 archive has been validated locally; it contains 794
training, 110 validation, and 225 test `dog` instances. An optional
random-initialization dog-only training experiment recorded four epochs in its
logs/checkpoint; epoch 2 was the only epoch evaluated. The result is
exploratory: the test split was inspected before training continued, and the
exact epoch-2 checkpoint was overwritten. The epoch-4 local checkpoint
successfully loads but was not evaluated. Neither checkpoint is part of
application inference or appropriate for performance claims. A loss
normalization flaw identified in the original run has since been corrected;
the existing checkpoints were trained with the old loss and have not been
retrained. The model's dog-only PCK@0.1 was 0.000881 (2/2,269 keypoints),
below an oracle-box-center baseline of 0.051565 (117/2,269); both are
diagnostic on the already-inspected test split. See
[`reports/canine_pose_evaluation.md`](../reports/canine_pose_evaluation.md).
Current app results remain COCO-17 or motion-only, never canine-pose results.

| Canine-pose milestone | Status |
| --- | --- |
| Training code implemented | Yes; AP-10K preparation and dog-only heatmap trainer |
| Training completed | Partial run only: four epochs logged/checkpointed; the configured 10 epochs were not completed |
| Checkpoint loaded | Yes; epoch-4 state loaded and produced a finite `(1, 17, 64, 48)` heatmap tensor in a local smoke test |
| Canine keypoints produced by inference | Yes on AP-10K still images with oracle boxes; exploratory epoch-2 predictions only |
| Independent labeled evaluation | No; official test data has been inspected and is diagnostic-only |
| Real dog-walking video tested with the canine model | No; no authorized video was available in the repository or local cache |
| Gait metrics validated | No |
| Canine feature integrated into the app | No; only COCO-17 or motion-only inference is enabled |

Placeholder peak, spacing, and phase cutoffs are in `docs/GAIT_METRICS.md`.

## Fallback

If torch, transformers, or the weights are missing, or pose throws, the clip
is still measured with OpenCV frame difference. `diagnostics.poseSkipReason`
says why. The request does not fail because pose failed.

## Cache

```bash
pip install -r requirements.txt
python scripts/cache_models.py
```

Weights go to `HF_HOME`, default `models/hf`. That directory is gitignored.

## Time and memory

An exploratory CPU profile of a 15.000-second 30 fps file made by repeating
a 5-second clip recorded sample time 0.949 s, pose including weight load
39.162 s, and peak RSS 1665.3 MB. The old timing script also reported 0.015 s
of gait math and 40.127 s total, but it incorrectly ran AP-10K gait formulas
on COCO-17 output. Those gait and total values are not valid for production
gait-performance comparison. The one-shot `analyze_clip.py` run returned
`pipeline: dog-pose` in 37.543 seconds on that same file; that legacy
identifier is now `coco-pose`. A new comparable benchmark has not yet been
run; see the correction in `docs/HOSTING.md`.
Loading both models in a new process, without a clip, took 4.02 seconds of
wall time. GitHub Actions built and smoke-tested the Docker image on October 22, 2026, but peak hosted RAM has not been measured.
Details are in `docs/HOSTING.md`.
