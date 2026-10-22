# Canine-pose model audit

**Status: no validated canine-pose checkpoint is available in this checkout.**
The current optional pose path uses a dog detector and a ViTPose++ checkpoint
whose output head is COCO-17. Its output remains labeled `coco-17`; selecting
the checkpoint's AP-10K backbone expert does not change that head. COCO-17 has
no neck or root-of-tail landmarks, so it is not accepted by the AP-10K gait
metrics. The application must keep those gait values `null` unless an actual
AP-10K-schema model passes the acceptance checks below. The OpenCV-motion
result is not pose estimation.

## Local evidence and blockers

The repository and local resources were inspected for this audit:

- No AP-10K, StanfordExtra, or other authorized canine annotations/images are
  present in the checkout.
- No labeled walking-video evaluation set or trained canine checkpoint is
  present. Synthetic gait tests validate formulas only.
- PyTorch is not installed in the active environment; no model weights are
  cached. The host has an Intel integrated GPU and no available CUDA device.
- Therefore model training, held-out canine accuracy, and video generalization
  were not measured. The current COCO-17 checkpoint was not promoted or
  re-labeled as a canine model.

## Dataset candidates and use constraints

| Dataset | Fit | Current access / rights evidence | Constraint |
| --- | --- | --- | --- |
| [AP-10K](https://github.com/AlexTheBad/AP-10K) | 17 points include neck and root of tail, matching the gait schema; 10,015 images across 54 species | Official README states CC BY 4.0 and links the dataset archive; source-image upstream restrictions still need review | Broad animal dataset; domestic-dog representation has not been established |
| [StanfordExtra](https://github.com/benjiebob/StanfordExtra) | 12k labeled dog instances, with paw, leg, and tail landmarks | Authors state annotations are MIT-licensed and require a form; images are obtained separately from Stanford Dogs | Its 20-point schema has no AP-10K neck point; separately sourced image terms must be confirmed before use |
| [Animal Pose](https://sites.google.com/view/animal-pose/) | Includes dogs and body landmarks | No broad reuse license was verified in the reviewed official material | Do not download, train on, or redistribute until image and dataset rights are resolved |

AP-10K's published order was cross-checked against the official README and
MMPose dataset config:

1. left eye, right eye, nose, neck, root of tail
2. left shoulder, left elbow, left front paw
3. right shoulder, right elbow, right front paw
4. left hip, left knee, left back paw
5. right hip, right knee, right back paw

The official AP-10K repository also links HRNet and ResNet checkpoints trained
on AP-10K. Their existence is not a PetLens evaluation result. They have not
been downloaded, their runtime integration has not been exercised here, and
the exact checkpoint/model-code license and domestic-dog coverage must be
reviewed before redistribution or product use.

## Reproducible data preparation

Once an authorized AP-10K archive is obtained and extracted with `annotations/`
and `data/` at its root, prepare one of its official split sets:

```powershell
python scripts/prepare_ap10k.py `
  --dataset-root C:\datasets\ap10k `
  --output-dir C:\datasets\ap10k-prepared `
  --split-number 1
```

The command checks the declared 17-keypoint order, image references, COCO
bounding boxes, visibility values, point bounds, and `num_keypoints`. It
preserves the official train/validation/test partitions; rejects reused image
IDs, paths, identity/source groups when supplied, and byte-identical images
across splits; then writes canonical JSON manifests. It does not download,
copy, or redistribute dataset images. If source metadata lacks identity or
video grouping, the manifest says that same-dog leakage cannot be ruled out.
Use `--skip-image-check` only for annotation-only inspection, never as evidence
that data are ready for training.

The source archive has not been acquired in this environment, so the command
has only been tested with generated fixtures. This validates the converter's
guards, not AP-10K itself.

## Acceptance gates before model integration

1. **Data provenance:** obtain authorized data and record exact archive,
   annotation version, license/attribution, upstream image terms, and canine
   species composition. Do not equate an animal-pose dataset with dog-only
   evaluation.
2. **Split integrity:** retain official splits or create identity/video-grouped
   splits; document duplicates and same-dog overlap. Do not use validation or
   test labels for training or threshold selection.
3. **Model provenance:** record architecture, initialization/checkpoint
   hashes, training config, software versions, random seeds, and output schema.
   A checkpoint is accepted only if its actual output channels match the
   versioned AP-10K schema.
4. **Held-out landmarks:** report per-keypoint and aggregate PCK/OKS on labeled,
   held-out dog images, stratified by visibility, pose, and breed/appearance
   where available. Compare against a documented baseline and include
   confidence intervals or per-image results.
5. **Walking-video review:** evaluate independent, labeled dog-walking clips
   across side views, direction, occlusion, and speed. Review overlays for
   left/right swaps, track switches, missing paws, and landmark drift. A
   single demonstration clip is not validation.
6. **Product gate:** only after gates 1–5 should a canine checkpoint be wired
   to AP-10K gait calculations. Keep the OpenCV motion fallback labeled as
   motion-only, and leave gait measurements unavailable on any schema mismatch
   or insufficient-quality pose.

Until these gates pass, no training, accuracy, or walking-video generalization
claim is supported by this repository.
