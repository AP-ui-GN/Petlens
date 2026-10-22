# Setup check

`python scripts/check_setup.py` reports the local analysis toolchain. The command is read-only: it does not download weights, it does not import PyTorch, and it does not run the pose model.

## What the report includes

The text report is built by `collect_setup` and `format_setup` in `gait_engine/setup_check.py`.

- Python version.
- OpenCV version, or `not importable`.
- Whether cached files exist for the two model ids named in `gait_engine/pose_backend.py`:
  - detector `PekingU/rtdetr_r50vd_coco_o365`
  - pose `usyd-community/vitpose-plus-base`
- For each id: config present or absent, weights present or absent. A weight file counts only when `model.safetensors` or `pytorch_model.bin` is a real non-empty file. A broken symlink is absent.
- Pose schema from the cached `config.json` `id2label`, when that file is present. The schema is `coco-17` only when channels 0–16 match the COCO short names, including `r_ear` at channel 4. Any other label list is `unverified`. Channel 4 is printed as the string stored in the file. The check does not rename it.
- Whether `torch` and `transformers` can be found with `importlib.util.find_spec`. They are not imported.
- `poseReady`: true only when both of those packages are findable, both weight files are present, and the pose schema is `coco-17`. This means the cache looks usable. It is not an accuracy number and it is not a validation result.
- `fallbackReady`: true when OpenCV imports.
- `downloadsWeights`: always false.
- The sentence `This command does not download weights.`

Text mode exits 0 when OpenCV imports and 1 when it does not. Missing weights are reported and are not a failure, because a new clone does not have them. `--json` prints the same report and exits 0 even when OpenCV is missing, so a probe can read `fallbackReady`.

## CPU and CUDA

This command does not report CPU or CUDA. It never loads the model, so it cannot say which device a later run will use.

Device choice happens later, on the first `VitPoseCoco17Backend.process()` call, inside `_ensure_loaded`: `cuda` if `torch.cuda.is_available()` else `cpu`. That choice is not part of the setup report.

## Where the weights come from

`hf_home()` in `gait_engine/pose_backend.py` picks the cache directory:

- `HF_HOME` when that environment variable is set
- otherwise `<repository>/models/hf`

The check looks under that directory, or under a `hub/` child of it, for `models--<org>--<name>/snapshots/<revision>/`. The first `process()` call loads the two ids above with `transformers` `from_pretrained`. That call reads this cache. If the snapshot is already there, the revision recorded in the snapshot path can be returned by `_revision`. This repository does not put a checkpoint URL in the setup check, and this document does not add one.

A clone with an empty cache is not pose-ready. `scripts/check_setup.py` will not fetch the missing files. Whether a later `process()` call downloads them depends on the installed Hugging Face client, the cache, and the network. That download is outside this command.

`AP10K_DATASET_INDEX` is 3. At inference it selects a backbone expert. It does not switch this checkpoint to an AP-10K keypoint head. The output schema remains `coco-17`. Channel 4 of that head is the right ear.
