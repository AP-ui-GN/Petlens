# Human paw annotation preparation

This offline pipeline prepares human physical-paw references and **partial AP-10K
COCO annotations** for future RTMPose-m fine-tuning. It does not train, run pose
inference, or use model predictions as ground truth. Only Python's standard
library and the existing OpenCV installation are required.

Run from the repository root, using a new output directory:

```bash
python -m training.prepare_paw_annotations --output-dir reports/paw-annotation-data-v1
python -m unittest discover -s tests -p test_paw_annotation_data.py -v
```

`training/paw_annotation_sources.json` pins SHA256 hashes of the existing videos,
prediction JSON, annotation exports, source manifests and repository keypoint
schema. Inputs include locally cached files under ignored `tmp/`; this is not a
self-contained downloadable dataset. Missing or changed sources fail explicitly.
The Dalmatian original and inference derivative are both hashed. Frames are
decoded from the verified inference-source videos, with dimensions, frame count,
FPS and timestamps checked against the saved metadata. No overlays are used.

## Output contract

| File | Purpose |
|---|---|
| `physical-reference.json` | Deduplicated human A/B labels, source references, frame times and original prediction context in separate fields. |
| `original-annotations.json` | Original parsed exports, preserving annotator, exposure, events, continuity and other fields. Input files remain unchanged. |
| `images/{dalmatian,dog02}/*.png` | Lossless frames decoded from verified videos; hashes are recorded. Images are locally generated and git-ignored. |
| `anatomical-review-template.json` | Per-frame A/B anatomical review queue; all anatomical channels initially null. |
| `accepted-anatomical-reviews.json` | Explicit human anatomical decisions supplied to this build, if any. |
| `train.coco.json` | Dalmatian images and only anatomically reviewed human point targets. |
| `exploratory_evaluation.coco.json` | dog02 equivalents; never training or model selection. |
| `manifest.json` | Input/output hashes, builder hash, OpenCV version, split membership, deduplication counts and excluded-target reasons. |

Physical A/B is **not** anatomical left/right, image side, or a model channel.
Human coordinates are retained even if the model is inaccurate, low confidence,
or missing a candidate. No distance threshold, confidence threshold, nearest-point
matching, interpolation or automatic anatomical mapping is used.

The source annotation schema is `physical-hind-tracks`, version 1. `visible`
requires a finite in-image human coordinate. `occluded`, `uncertain`/`ambiguous`
and `unmarked` require null coordinates. These states remain distinct in the
physical reference. Identical completed paw labels are deduplicated; an unmarked
placeholder cannot erase a label. Conflicting completed labels or metadata fail
rather than silently choosing an export. JSON duplicate keys also fail.

## Anatomical review and future fine-tuning

Copy the generated review template to a separate human-edited file. For each
visible point you can anatomically verify, set `anatomicalKeypoint` to
`left_back_paw` or `right_back_paw`, with `reviewer` and a concrete `evidence`
description. Review original images and adjacent frames. Do not fill a global
"A=left" assumption or use RTMPose label names to decide. Leave unresolved
entries null. Label/image hashes bind every review to its exact reference.

```bash
python -m training.prepare_paw_annotations \
  --anatomical-reviews /path/to/human-reviewed-anatomy.json \
  --output-dir reports/paw-annotation-data-reviewed
```

Exported COCO targets use the repository's AP-10K 17-channel order. Only reviewed,
visible human points get `(human_x, human_y, 2)`. All other channels use COCO's
unlabeled `[0, 0, 0]` sentinel: **these zeros are not coordinates or negative
location targets**. The future RTMPose/SimCC training configuration must mask
their loss weights. There are no front-paw, hip or knee targets unless humans
annotate them through a future schema extension. The current exporter never
substitutes those predictions for labels.

An occluded state alone has no location target. A partially hidden pose can use
an existing visible point only where the reviewer can actually locate the paw.
Training on human-inferred occluded locations (`v=1`) would need an explicit new
annotation schema for those human coordinates and their uncertainty; it is not
enabled by this builder. Do not guess fully hidden coordinates to fill the file.

COCO `bbox` currently describes the full frame, not a human dog-box annotation.
This avoids cropping away corrected points. Review dog crops before a useful
top-down experiment; a saved detector box may provide a proposal but is not a
verified label. The output uses the dataset root as `data_root` and relative
`file_name` paths. Its COCO layout is prepared; an installed MMPose loader and
RTMPose training configuration have **not** been exercised here.

The existing `training/train_pose.py` trains a separate ResNet heatmap model; it
is not the RTMPose fine-tuning entry point. A future RTMPose run needs the matching
trainable pretrained checkpoint and configuration. The cached inference ONNX file
is not a drop-in training checkpoint. No weights were obtained in this task.

## Inventory and first experiment

| Source | Stored frames | Frames with visible labels | Visible physical points | Occluded slots | Unmarked slots | Anatomical targets now |
|---|---:|---:|---:|---:|---:|---:|
| Dalmatian, training | 46 | 42 | 79 | 10 | 3 | 0 |
| dog02, exploratory evaluation | 29 | 28 | 55 | 1 | 2 | 0 |
| Total, deduplicated | 75 | 70 | 134 | 11 | 5 | 0 |

Six repeated dog02 A labels were removed. No new human coordinate is required to
retain the 134 existing visible physical references. **None can currently be
assigned directly to an anatomical AP-10K output channel.**

Minimum practical next annotation pass: anatomically adjudicate the **79 existing
Dalmatian points across 42 frames** you intend to train on, confirming a consistent
paw landmark and reviewing crops. Anatomically adjudicate the **55 dog02 points
across 28 frames** before evaluating left/right localization there. Unresolvable
points stay unlabeled; these counts are a review queue, not a required statistical
sample size or permission to force identity. Review crossings and partial
occlusions explicitly. Front paws and major joints need additional human point
labels before those channels can be fine-tuned or evaluated.

After review, start with a small masked hind-paw localization fine-tuning pilot
of the existing RTMPose-m, using Dalmatian only and a fixed training schedule.
First verify on a few reviewed frames that coordinate transforms and masked
losses work. Compare saved-pretrained and subsequently fine-tuned localization
against the same human coordinates; retain difficult points even if pretrained
predictions miss them. dog02 remains exploratory reporting only, never checkpoint
selection or hyperparameter tuning.

The present single training sequence supports a technical feasibility/overfit
check, not a generalization result. Meaningful model selection additionally needs
a separately reserved, anatomically annotated development sequence; none is
available under the current split policy. No defensible minimum video count for
generalization follows from this inventory. Further gait-event/stride claims need
their own temporal identity and event validation and are outside this dataset.
