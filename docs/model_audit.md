# Canine-pose model audit

**Status: no validated production canine-pose checkpoint is available in this checkout.**
The current optional pose path uses a dog detector and a ViTPose++ checkpoint
whose output head is COCO-17. Its output remains labeled `coco-17`; selecting
the checkpoint's AP-10K backbone expert does not change that head. COCO-17 has
no neck or root-of-tail landmarks, so it is not accepted by the AP-10K gait
metrics. The application must keep those gait values `null` unless an actual
AP-10K-schema model passes the acceptance checks below. The OpenCV-motion
result is not pose estimation.

## Local evidence and blockers

The repository and local resources were inspected for this audit:

- The official AP-10K archive was downloaded to the user cache, verified as a
  readable ZIP, extracted outside the repository, and prepared using official
  split 1. It contains 794 dog instances in train, 110 in validation, and 225
  in test; these are still image annotations, not walking-video labels.
- No StanfordExtra images or labeled walking-video evaluation set are
  present. The only canine checkpoints are experimental local cache outputs
  described below; none is tracked or integrated.
- The application environment does not include PyTorch, Transformers,
  Ultralytics, or ONNX Runtime. An optional CPU-only PyTorch training
  environment was installed separately; the host has an Intel integrated GPU
  and no available CUDA device.
- Hardware inspection reported an Intel Core Ultra 9 386H (16 logical CPUs),
  32 GB system RAM, no dedicated GPU memory reported, and about 688 GB free on
  C:. Python is 3.12.10 and OpenCV is 4.10.0. The application environment has
  no `torch`, `transformers`, `ultralytics`, or `onnxruntime`.
- A fresh random-initialization, corrected-loss ResNet-18 run completed 30
  epochs and selected its checkpoint by validation loss. On the official
  dog-only validation split it achieved PCK@0.1 of 0.425725 (470/1,104 visible
  keypoints), versus 0.037138 (41/1,104) for the oracle-box-center baseline.
  All 17 channels exceeded their per-keypoint baselines; tail-root PCK was
  only 0.035. This is a validation baseline pass only: the split selected the
  checkpoint and controlled early stopping, and the evaluation uses
  ground-truth boxes on still images. It is not independent evidence or
  video/gait validation. The checkpoint remains in the local cache and is not
  integrated. See
  `reports/canine-pose-validation/index.html`.
- The earlier epoch-2 test result (0.000881 versus a 0.051565 box-center
  baseline) belongs to a checkpoint trained with the old loss and to a test
  split inspected before training continued. It is a historical diagnostic,
  not a result for the fresh run; see `reports/canine_pose_evaluation.md`.
- Review found the original trainer divided sparse heatmap error by all
  spatial pixels, allowing background pixels to dominate. The trainer now
  normalizes each labeled landmark's spatial squared error by its target
  heatmap energy; the fresh 30-epoch run used the corrected loss.
- The official AP-10K README states CC BY 4.0, while the included COCO license
  metadata labels its image license MIT and links to a different license URL.
  This discrepancy is documented and must be resolved before public model or
  dataset redistribution.

## Dataset candidates and use constraints

| Dataset | Fit | Current access / rights evidence | Constraint |
| --- | --- | --- | --- |
| [AP-10K](https://github.com/AlexTheBad/AP-10K) | 17 points include neck and root of tail; 10,015 images across 54 species | Official README states CC BY 4.0; archive's image-level COCO license metadata instead says MIT | Split 1 contains 794/110/225 dog instances (train/val/test). Image-source terms need clarification, and the images do not establish walking-gait performance |
| [StanfordExtra](https://github.com/benjiebob/StanfordExtra) | 12k labeled dog instances, with paw, leg, and tail landmarks | Authors state annotations are MIT-licensed and require a form; images are obtained separately from Stanford Dogs | Its 20-point schema has no AP-10K neck point; separately sourced image terms must be confirmed before use |
| [Animal Pose](https://sites.google.com/view/animal-pose/) | Includes dogs and body landmarks | No broad reuse license was verified in the reviewed official material | Do not download, train on, or redistribute until image and dataset rights are resolved |
| [Ultralytics Dog-Pose](https://docs.ultralytics.com/datasets/pose/dog-pose/) | 8,476 Stanford Dogs images (6,773 train / 1,703 validation), 24 named points; strongest dog-specific fit | The vendor documents a 337 MB release archive but does not establish a separate dataset license in the reviewed page; images derive from Stanford Dogs. Ultralytics software is AGPL-3.0, with the vendor identifying commercial/SaaS use as requiring an Enterprise license | Not downloaded or integrated: image rights and model/software license compatibility with PetLens must be resolved first |

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

The official AP-10K archive is stored outside the repository. The verified
archive SHA-256 and prepared counts are in `docs/dataset_provenance.md` and
`training/dataset_manifest.json`. For another authorized copy, prepare one of
its official split sets:

```powershell
python training/prepare_dataset.py `
  --dataset-root C:\datasets\ap10k `
  --output-dir C:\datasets\ap10k-prepared `
  --split-number 1
```

The command validates the declared 17-keypoint order, image references,
decoded image dimensions, COCO bounding boxes, visibility values, point bounds,
and `num_keypoints`. It preserves official partitions; rejects reused image
IDs, paths, groups when supplied, and byte-identical images across splits; and
writes canonical splits plus category counts. This environment's actual
archive passed preparation. Since the source has no supported dog/video
identity field, same-dog leakage cannot be ruled out.

## Training and evaluation implementation

`training/train_pose.py` implements an optional dog-only, top-down ResNet-18
heatmap model. It uses AP-10K dog-category crops and the official train and
validation partitions, correct left/right channel swaps on horizontal flips,
visible/occluded heatmap targets, validation-loss checkpoint selection,
early stopping, atomic best/last checkpoints, JSONL metrics, and resume
support. It initializes randomly; it does not reuse the human COCO-17 head or
download an unverified weight file. The existing detector remains separate.

The optional stack is in `requirements-training.txt`. The fresh corrected-loss
run completed 30 epochs on CPU in 1,205.218 seconds; its checkpoint is retained
outside the repository. The older epoch-2 checkpoint used for the historical
test diagnostic was overwritten. Current trainer runs use unique experiment
directories, fingerprint their data/config/checkpoint artifacts, and preserve
parent checkpoint identity on resume. AP-10K's dog-only subset is small, has
no walking-video labels, and its digitigrade hip/knee labels do not map
directly to literal canine anatomy. Product gait metrics therefore remain
gated.

## Held-out pose evaluation

`training/evaluate_pose.py` supports the AP-10K dog-only validation and test
splits and writes machine-readable metrics, a human-readable report,
predictions, and optional labeled overlays. `scripts/evaluate_ap10k.py`
provides the underlying fixture-tested PCK/error evaluator. It reports
confidence-filtered PCK at explicit thresholds, mean pixel and normalized
errors, per-keypoint results, and visible-versus-occluded scores. It uses
ground-truth boxes, so it measures pose localization only; it does not measure
dog detection, tracking, real-video behavior, or gait. Example:

```powershell
python training/evaluate_pose.py `
  --config training\dataset_config.yaml `
  --split val `
  --require-baseline `
  --checkpoint outputs\ap10k-dog\checkpoint_best.pt `
  --visualizations-dir reports\canine-pose-validation
```

The current corrected-loss model's validation metrics and charts are in
`reports/canine-pose-validation/`. The validation split selected the checkpoint
and is not independent. The historical test metrics in
`reports/canine_pose_metrics.json` are from the earlier epoch-2 model only;
that split was inspected before training continued and the corresponding
checkpoint was overwritten. Do not use either result as independent evidence
or a product-performance claim. A separate rights-cleared dog dataset is
required for independent evaluation.

## Acceptance gates before model integration

1. **Data provenance:** resolve the AP-10K README/COCO metadata license
   discrepancy and record exact archive, annotation version,
   license/attribution, image-source terms, and canine species composition.
   Do not equate an animal-pose dataset with dog-only evaluation.
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

Until these gates pass, no canine-pose accuracy or walking-video
generalization claim is supported by this repository.
