# Body-reference comparison experiment

- Source predictions: `../full-video/rtdetr-rtmpose-full-video.json`.
- Frames: 165; original predictions used unchanged; no interpolation.
- Existing raw-score threshold: 0.80.
- Reference availability requires the dog detection and every method landmark at or above 0.80.
- Right-paw coordinates are normalized as `(paw - reference center) / reference length`; paw itself must score at least 0.80.
- Paw jump warning uses the existing experimental cutoff of 0.35 reference lengths per frame.

## Landmark-definition note

AP-10K names Left Hip and Right Hip as paired animal-side landmarks. Its README notes that for digitigrade animals such as dogs, its `hip` label is used at the knee-level joint, not necessarily the anatomical pelvis. Method A is therefore reported as the project's current shoulder + AP-10K hip reference, not as a verified shoulder-to-pelvis measurement.

## Summary

| Measure | Method A: shoulders + AP-10K hips | Method B: neck + tail root |
|---|---:|---:|
| Reference passes threshold | 142/165 (86.1%) | 75/165 (45.5%) |
| Paw-relative positions available (reference + paw pass) | 140/165 | 75/165 |
| Valid consecutive length comparisons | 124 | 61 |
| Median length change between valid neighbors | 1.48 px (2.40%) | 1.30 px (1.37%) |
| 95th-percentile length change | 5.17% | 3.64% |
| Length variation across valid frames (coefficient of variation) | 14.89% | 16.38% |
| Paw jumps > 0.35 on fully reliable adjacent pairs | 0 | 0 |

Length changes are reported only for consecutive frames where both references pass the same confidence rule. The coefficient of variation measures total frame-to-frame size variation and can reflect real pose/view changes, not just model noise.

On the **50 same adjacent frame pairs** where both references pass, median percentage length change is 2.49% for A and 1.50% for B.

## Examples at the previously inspected frames

| Frame | A reference center / length | A paw (x,y) | B reference center / length | B paw (x,y) |
|---:|---|---|---|---|
| 45 | (197.9,141.0) / 71.0px (below threshold) | (-0.523,0.548) (below threshold) | (200.8,110.0) / 93.7px (below threshold) | (-0.426,0.746) (below threshold) |
| 55 | (199.6,141.0) / 76.0px (below threshold) | (-0.489,0.542) (below threshold) | (205.7,108.2) / 105.3px (below threshold) | (-0.410,0.703) (below threshold) |
| 66 | (205.4,142.4) / 82.2px (pass) | (-0.510,0.505) (pass) | (209.9,106.7) / 108.1px (pass) | (-0.430,0.714) (pass) |
| 77 | (214.9,142.6) / 83.5px (below threshold) | (-0.524,0.548) (below threshold) | (220.9,103.2) / 112.7px (pass) | (-0.442,0.754) (pass) |
| 100 | (236.9,137.7) / 73.0px (below threshold) | (-0.493,0.620) (below threshold) | (245.7,103.3) / 103.4px (pass) | (-0.433,0.771) (pass) |

For comparison, normalized paw positions are shown even when a reference fails the 0.80 score check; those values are exploratory and not counted as usable.


## Largest observed changes

### Method A: Shoulder + AP-10K hip

Largest valid consecutive reference-length changes:
- Frames 81→82: +6.63px (9.1%).
- Frames 59→60: +4.92px (7.2%).
- Frames 135→136: -3.63px (7.1%).
No checked right-hind-paw pair exceeded 0.35 reference lengths.
Across all dog-detected adjacent pairs with paw scores passing, including low-confidence references:
- Frames 21→22: 0.527 lengths (at least one reference fails).

Largest checked paw movement: frames 65→66, 0.317 reference lengths.

Largest paw movement across all score-passing paw pairs: frames 21→22, 0.527 lengths (at least one reference fails).

### Method B: Neck + tail root

Largest valid consecutive reference-length changes:
- Frames 161→162: -3.12px (4.8%).
- Frames 122→123: -3.93px (4.2%).
- Frames 100→101: -4.23px (4.1%).
No checked right-hind-paw pair exceeded 0.35 reference lengths.

Largest checked paw movement: frames 24→25, 0.202 reference lengths.

Largest paw movement across all score-passing paw pairs: frames 21→22, 0.336 lengths (at least one reference fails).

## Interpretation limits

These calculations compare consistency of model-derived reference geometry, not anatomical accuracy. Stable lengths do not prove that the landmarks are correctly placed; confidence scores are not calibrated probabilities; and changes can reflect actual body pose, camera perspective, occlusion, or prediction noise. No manual ground-truth labels were used.

Official landmark sources: [AP-10K keypoint definitions and FAQ](https://github.com/AlexTheBad/AP-10K#keypoint-definition) and [MMPose AP-10K keypoint mapping](https://github.com/open-mmlab/mmpose/blob/main/configs/_base_/datasets/ap10k.py).
