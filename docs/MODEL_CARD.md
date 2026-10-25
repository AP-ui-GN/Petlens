# PetLens model card

PetLens measures a walking clip. It does not diagnose pain, injury, or disease.

## What runs

| Pipeline | When | What it measures |
| --- | --- | --- |
| `opencv-motion` | Default; also used if optional inference is unavailable | Frame-to-frame picture change; when detector dependencies and weights are available, dog-in-frame coverage is retained without pose output. |
| `coco-pose` | Only when `PETLENS_ENABLE_EXPERIMENTAL_COCO_POSE=true` and the pose dependencies and weights load | Experimental detector output plus 17 human COCO joints. This checkpoint has no AP-10K head and is not canine pose. |

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
training, 110 validation, and 225 test `dog` instances. A fresh, randomly
initialized dog-only ResNet-18 run used the corrected heatmap loss and
completed 30 epochs. Its validation-selected checkpoint reached PCK@0.1
**0.425725 (470/1,104 visible keypoints)** on the official dog-only validation
split, versus **0.037138 (41/1,104)** for the oracle-box-center baseline; the
model's 95% image-bootstrap interval is [0.379068, 0.475340]. All 17 keypoint
channels also exceed their box-center validation baseline, although tail-root
PCK remains low at 0.035. This clears the baseline on validation only. The
same split selected the checkpoint and controlled early stopping, so the
result is development evidence, not an independent test result. It uses
oracle boxes on still images and says nothing about detection, walking-video
tracking, or gait. The checkpoint stays in the local cache and is not part of
application inference. Charts, metrics, and protocol caveats are in the
[`validation report`](../reports/canine-pose-validation/index.html), with a
separate [`measured highlights gallery`](../reports/petlens-positive-results/index.html).

The earlier epoch-2 test result (PCK@0.1 0.000881 versus 0.051565 for
box-center) came from a checkpoint trained with the old loss and from a test
split inspected before training continued. It is a historical diagnostic, not
a result for the corrected-loss model or independent evidence; see the
[historical test report](../reports/canine_pose_evaluation.md).

A bounded one-epoch CPU fine-tune from the corrected-loss checkpoint was
evaluated on the same development validation split on 2026-10-25. PCK@0.1
changed from 0.425725 to 0.431159, but validation loss worsened, the image
bootstrap intervals overlap, and several per-joint scores declined. It was
not promoted or integrated. The original epoch-30 checkpoint remains the
selected experimental model. See the
[training follow-up](../reports/canine-pose-training-2026-10-25.md).
Default app results are motion-only, optionally with detector metadata. The
COCO-17 experiment is disabled unless explicitly enabled; it is never a
validated canine-pose result.

| Canine-pose milestone | Status |
| --- | --- |
| Training code implemented | Yes; AP-10K preparation and dog-only heatmap trainer |
| Training completed | Yes; 30 epochs with the corrected loss, selected by validation loss |
| Checkpoint loaded | Yes; best checkpoint evaluated on AP-10K validation images |
| Canine keypoints produced by inference | Yes on AP-10K still images with oracle boxes; not in app inference |
| Independent labeled evaluation | No; validation is development-only and prior test inspection prevents an independent test claim |
| Real dog-walking video tested with the canine model | No; the supplied gait-paper clip was tested with detector-only processing, without canine pose |
| Gait metrics validated | No |
| Canine feature integrated into the app | No; only COCO-17 or motion-only inference is enabled |

Placeholder peak, spacing, and phase cutoffs are in `docs/GAIT_METRICS.md`.

## Fallback

Experimental pose is disabled by default. The clip is measured with OpenCV
frame difference, and if the dog detector can run independently, its tracked
dog-frame share, multiple-dog flag, and person-present flag are kept. Pose
coordinates and gait metrics remain unavailable. If detector dependencies or
weights are also missing, the result is motion-only. For local pose-output
inspection only, set `PETLENS_ENABLE_EXPERIMENTAL_COCO_POSE=true`. Missing
weights or inference failures still fall back to motion and dog detection.
`diagnostics.poseSkipReason` says which path ran and why. The request does not
fail because either model failed.

The supplied 5-second, 60-frame gait-paper OGV was run through the current
Python analysis pipeline with pose downloads disabled. RT-DETR found one dog
on all 12 scheduled detector samples, reported a person present, and found no
multiple-dog ambiguity. `dogFramesShare=0.2` is 12 accepted detections divided
by all 60 sampled frames: detections run every fifth frame, and skipped frames
are not inferred. It is not a claim that the dog occupied only 20% of the
video. Pose landmarks, stride symmetry, and gait metrics remained unavailable.

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
