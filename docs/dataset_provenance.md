# AP-10K dataset provenance

## Source and license

- Dataset: [AP-10K](https://github.com/AlexTheBad/AP-10K), official Google
  Drive archive linked by the authors.
- Archive SHA-256:
  `420980abb135d6f66bcc8e29f289a46081214016192ae197ad24bc1525c8e62c`
- The official README states **CC BY 4.0** and requests citation of Yu et al.,
  *AP-10K: A Benchmark for Animal Pose Estimation in the Wild* (NeurIPS 2021).
- The downloaded COCO annotation documents separately contain a license entry
  named **“The MIT License”** pointing to `mit.edu/~amini/LICENSE.md`, and
  every image refers to that entry. This conflicts with the README's dataset
  license declaration. The discrepancy and underlying image-source terms must
  be resolved before redistributing images, derived weights, or using them in
  a public/commercial product.
- The archive and extracted images remain in the user's local cache, outside
  this repository. No dataset image or model checkpoint is tracked here.

## Verified contents

The archive was `3.16 GiB`, contained 10,027 entries, and passed Python
`zipfile.testzip()` with no corrupt member. All images in official split 1
were extracted locally, decoded with OpenCV, checked against annotation
dimensions, and SHA-256 hashed for cross-split duplicate checks.

| Official split 1 | Images | Instances | `dog` instances | `dog` images |
| --- | ---: | ---: | ---: | ---: |
| Train | 7,023 | 9,122 | 794 | 700 |
| Validation | 995 | 1,272 | 110 | 100 |
| Test | 1,997 | 2,634 | 225 | 200 |
| **Total** | **10,015** | **13,028** | **1,129** | **1,000** |

The split contains 50 represented species categories; the full dataset is
described by the authors as 54 species. The trainer explicitly filters to the
`dog` category rather than mixing all animal classes into a dog model. AP-10K
contains still images, not walking videos. The annotations expose no supported
dog identity or source-video field, so same-dog overlap across official splits
cannot be ruled out. Exact duplicate image files were checked across splits.

`training/dataset_manifest.json` is the generated manifest from the validated
official split 1. Prepared canonical splits and original data are not stored in
the repository.

## Schema and intended use

The versioned channel ordering and topology are in
`training/canine_keypoint_schema.json`; the Python source of truth is
`gait_engine.pose_backend.AP10K_KEYPOINTS`. AP-10K annotates 17 points across
animal species. Its README states that for digitigrade animals such as dogs,
the labels `hip` and `knee` denote the knee and ankle, respectively. Those
channel names must not be read as literal canine anatomy without a validated
remapping. No gait metric is inferred from the AP-10K labels until that
semantics and real side-view walking clips are validated.

## Reproduction

1. Obtain the archive from the official AP-10K README, verify its source and
   license terms for the intended use, then extract it outside the repository.
2. Run `python training/prepare_dataset.py --dataset-root <ap-10k-root>
   --output-dir <prepared-dir> --split-number 1`.
3. Set paths in `training/dataset_config.yaml`, or pass `--dataset-root` and
   `--prepared-dir` to the training and evaluation scripts.
4. Install the optional stack in `requirements-training.txt` in a separate
   environment. For a CPU-only Windows install, use the official PyTorch CPU
   wheel index:

   ```powershell
   python -m pip install PyYAML==6.0.2
   python -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
   ```

5. The official test predictions were already inspected during this
   development session. They are permanently diagnostic-only for this
   checkpoint family; do not use this split for selection or make independent
   performance claims. A future evaluation needs a separately sourced,
   rights-cleared dog-pose set that has not informed training or model
   decisions. Every training invocation writes to a new
   `experiment-<id>` directory, including resumed runs.
