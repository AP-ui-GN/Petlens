# PetLens V2 portable Colab pilot

This package carries the original RTMPose-m AP-10K checkpoint, the CPU-verified
75,266-parameter adapter, unchanged fixed pilot config, validated Dalmatian labels,
all 46 referenced PNGs, exact derived splits, schema and verification evidence.
No videos, dog02 images/labels, model alternatives, environments, caches, credentials,
or repository history are copied. Original manifests retain historical provenance
paths (including dog02 metadata); these paths are not needed at runtime.

## Transfer without Git

1. In Codespaces Explorer, download `artifacts/petlens-colab-100step.zip`,
   `artifacts/petlens-colab-100step.zip.sha256`, and
   `artifacts/PetLens_100step_Colab.ipynb` (right-click → Download).
2. Open the notebook using Colab **File → Upload notebook**. Keep your T4 runtime.
3. Upload the ZIP and checksum via Colab's left **Files → Upload** button.
   The notebook verifies the outer ZIP before extracting into `/content`.
4. Run notebook cells in order. **Stop after Setup and preflight to inspect results.**
   Training has its own clearly labeled cell. That cell executes exactly one
   fresh 100-step pilot and then evaluates the final checkpoint.
5. Run the download cell to save `petlens-pilot-results.tar.gz` to your computer.
   Download before disconnecting: `/content` is temporary.

The extracted root is `/content/petlens-colab-100step`. The equivalent commands,
after extraction and changing into that directory, are:

```bash
python training/rtmpose_paw_v2/colab/verify_package.py
bash training/rtmpose_paw_v2/colab/setup.sh
# Setup stops after checks. Only the following command starts training:
bash training/rtmpose_paw_v2/colab/run.sh train
```

Setup records the host Python, installed torch and NVIDIA driver, then creates
`/content/petlens-env` using pinned uv 0.9.9 and CPython 3.10.16. It installs
PyTorch 2.1.0+cu118, torchvision 0.16.0+cu118, compiled MMCV 2.1.0 for that exact
ABI, and the same shared package pins as the verified CPU environment.
It leaves Colab's kernel packages intact. Software downloads require internet;
this is a portable **input** package, not an offline wheelhouse. The installed
GPU dependency closure is recorded with `pip freeze --all`; upstream CUDA
transitive wheels are resolved by pip rather than supplied in this archive.

A modern driver can run the older CUDA 11.8 wheel runtime; the `CUDA Version`
shown by `nvidia-smi` need not equal 11.8. No system CUDA toolkit replacement,
NVIDIA driver install, MMCV source compilation, or runtime Python downgrade is
needed. If a pinned dependency or CUDA test fails, stop and retain its output;
do not upgrade torch/MMCV independently.

Preflight checks Python/ABI versions, NVIDIA T4 compute capability 7.5, real
CUDA MMCV NMS, and a real model forward/backward on one annotated crop with finite
loss and adapter gradients. **No optimizer update occurs during preflight.**
The existing CPU checker verifies strict checkpoint keys/tensors, all train and
diagnostic images/pipelines, target masking and metric counts. Its new report
is written to `outputs/checkpoint-preflight.json`; recorded CPU evidence stays
unchanged. CUDA execution must pass on the actual Colab runtime; it has not
been executed in GPU-less Codespaces.

## Fixed experiment and outputs

Seed 20261104, 100 iterations, batch 4, FP32, 256×256, AdamW lr 1e-5,
weight decay 0, gradient clipping 1; no stochastic augmentation, EMA, LR scaling,
sweep, early stopping, resume or best-checkpoint selection. Only `head.paw_delta`
is trainable; other 15 channels use the frozen original branch.

| Split | Frames | Visible targets | Role |
|---|---:|---:|---|
| pilot-train (46–65) | 20 | 39 | optimizer |
| buffer-excluded (66–75) | 10 | 20 | excluded |
| temporal-diagnostic (76–90, ambiguous boxes omitted) | 10 | 17 | diagnostic only |

Frames 78 and 85 are excluded because their saved detections are ambiguous.
The original source keeps 42 annotated frames / 79 targets unchanged.
The same-video diagnostic is not independent validation or evidence of
full-body/gait/generalization improvement. Do not tune or select on it.

`train` rechecks inputs/CUDA, evaluates the zero-adapter original baseline,
runs the fixed pilot, and evaluates the complete custom candidate. Outputs:

- `outputs/rtmpose-paw-v2-pilot/iter_100.pth`: final adapter **and** original weights.
- `outputs/rtmpose-paw-v2-pilot/`: resolved config, training log and final validation.
- `outputs/evaluation/{baseline,candidate}.json`: left/right/pooled mean, median,
  p90 pixel error, fractions within 10/20 px and swap-closer fraction.
- `outputs/evaluation/{baseline,candidate}.pkl`: paired per-frame predictions.
- Host/dependency/CUDA reports, input SHA256 manifest, CPU evidence, split audit,
  provenance and complete training source are saved with the results.
- `/content/petlens-pilot-results.tar.gz`: downloadable results archive.

The stock MMPose head cannot retain the trained adapter. Load the candidate
with the supplied custom config/code. Re-running `train` with an existing pilot
output directory is rejected; use a fresh extraction if a new run is intended.
A failed training/evaluation command stops immediately; partial outputs remain
in `/content` and can be manually downloaded. Never treat them as completed results.

## Rebuild and integrity

From the repository root:

```bash
python training/rtmpose_paw_v2/colab/build_package.py
```

The builder uses an explicit allowlist, checks the original checkpoint hash,
source annotation manifest hashes, all image hashes and split audit hashes,
then verifies the staged payload and every ZIP member. `PACKAGE_MANIFEST.json`
records byte sizes and SHA256 of every payload file (excluding itself).
The adjacent ZIP checksum covers the complete archive, including that manifest.
Runtime outputs and installed software are not part of the immutable input manifest.
`prepare.py` is preserved as source history for the CPU checker import; do not
rerun dataset preparation here, since external detector source files are omitted.

Official compatibility references:
- https://pytorch.org/get-started/previous-versions/ (2.1.0 / CUDA 11.8)
- https://download.openmmlab.com/mmcv/dist/cu118/torch2.1.0/index.html
- https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html
