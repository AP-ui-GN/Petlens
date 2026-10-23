# Canine Pose Evaluation

- Status: exploratory measurement, not an independent held-out result
- Model: PetLens AP-10K dog-only ResNet-18 heatmap (`2c408756-94ed-4ed8-be40-6efc615236f8`)
- Training: epoch 2 of 4 recorded epochs; random initialization; 99.156 seconds for the initial two-epoch run on CPU. The exact continuation duration is unavailable.
- Checkpoint: epoch-2 weights were overwritten during continuation. The epoch-4 checkpoint remains in the local cache, loaded successfully in a smoke test, and was not evaluated.
- Dataset: AP-10K official split 1, dog annotations only; 225 instances across 200 images
- Evaluation: pose localization using oracle ground-truth boxes. Detection, tracking, and gait are not evaluated.
- Labeled keypoints: 2,269 visible keypoints; all 225 dog instances had predictions
- PCK@0.05: **0 / 2,269 = 0**
- PCK@0.1: **2 / 2,269 = 0.000881**
- PCK@0.1 95% image-bootstrap interval: **[0, 0.002238]** (200 images, 1,000 replicates, seed 0)
- Mean pixel error: 362.365 px
- Mean normalized error: 0.798904 (pixel error divided by the square root of annotation-box area)
- Visible-keypoint miss rate at PCK@0.1: **2,267 / 2,269 = 99.912%**

## Baseline comparison

The oracle-box-center baseline places all 17 keypoints at the center of the
ground-truth annotation box. It uses the same dog instances and PCK
normalizer, and is included as a diagnostic comparison only.

| Method | PCK@0.05 | PCK@0.1 | PCK@0.1 95% image-bootstrap interval |
| --- | ---: | ---: | ---: |
| Epoch-2 model | 0 | 0.000881 | [0, 0.002238] |
| Ground-truth box center | 0.008815 | 0.051565 | [0.043630, 0.060505] |

The model performed substantially worse than this trivial baseline. This is
not useful canine-pose performance. The original training loss averaged
sparse heatmap error over every spatial pixel, allowing background pixels to
dominate. That normalization has since been corrected to normalize each
labeled landmark's spatial error by its target heatmap energy. Existing
checkpoints used the old loss and were not retrained after the fix.

## Limitations and protocol

The official test split was evaluated and inspected after epoch 2, before
training continued through epoch 4. The epoch-2 checkpoint was subsequently
overwritten. Therefore these metrics and intervals are retrospective
diagnostics only: they are not an independent held-out result, cannot guide
checkpoint selection, and cannot support performance claims. The epoch-4
checkpoint is not evaluated. The cache retains the epoch-2 prediction JSON,
but not the corresponding weights.

The test uses ground-truth dog boxes, so no detector failure rate is available.
AP-10K is a still-image dataset; this report does not measure video tracking,
walking, or gait. Its digitigrade `hip`/`knee` labels have species-dependent
meanings. Gait calculations remain gated. No authorized dog-walking video was
available in the repository or local cache.
