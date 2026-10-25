# Minimal canine-pose training run — 2026-10-25

## Outcome

Completed one resumable CPU fine-tuning epoch from the existing, schema-correct
AP-10K dog-only checkpoint. Do **not** promote the candidate: it gained 6/1,104
visible landmarks at PCK@0.1 on the same development validation split
(+0.54 percentage points), but validation loss worsened, the image-bootstrap
intervals overlap, and several joint scores fell. The run did not establish a
reliable generalization improvement. The existing epoch-30 checkpoint remains
the selected checkpoint; neither checkpoint is integrated into production.

The model has an AP-10K 17-channel output trained on real dog annotations. It
is an experimental still-image pose model evaluated with ground-truth boxes;
it is not the app's inference model. Production remains motion-only by
default. The optional ViTPose path remains human COCO-17, not canine pose.

## Dataset and provenance

- AP-10K official split 1, dog category only; reused the local verified
  archive and prepared files under `%USERPROFILE%\.cache\petlens\datasets`.
- Train: 700 dog images / 794 instances; validation: 100 / 110; test: 200 /
  225. Only train and validation were used. The historically inspected test
  split was not opened or evaluated in this run.
- AP-10K annotates still images, not walking video. Source annotations do not
  provide dog identity/video grouping, so identity leakage cannot be ruled
  out. The archive README says CC BY 4.0, while included COCO metadata says
  MIT; image-source rights remain unresolved. See
  [`dataset_provenance.md`](../docs/dataset_provenance.md). No images or
  dataset files were copied into the repository.
- Model: ResNet-18 top-down heatmaps, random initialization in the original
  baseline; AP-10K schema `petlens.ap10k-17.v1`, 17 outputs. One additional
  epoch resumed optimizer and scheduler state from the baseline.

## Evaluation

Both checkpoints were evaluated on the identical 110-instance official
validation split with the same evaluator, 17 landmarks, oracle ground-truth
boxes, and the box-center baseline. This is development evidence: this split
was already used to select the original checkpoint and controls early
stopping. Do not treat the result or its confidence interval as independent
test evidence.

| Metric | Existing baseline, epoch 30 | One-epoch candidate, epoch 31 |
|---|---:|---:|
| PCK@0.05 | 0.267210 (295/1,104) | 0.275362 (304/1,104) |
| PCK@0.1 | 0.425725 (470/1,104) | 0.431159 (476/1,104) |
| PCK@0.1, 95% image-bootstrap CI | [0.379068, 0.475340] | [0.382276, 0.478649] |
| Mean normalized error | 0.222851 | 0.216505 |
| Mean pixel error | 111.92 px | 109.87 px |
| CPU model-forward time per dog crop | 33.67 ms | 33.76 ms |
| Validation loss | 0.841387 | 0.848593 |
| Box-center PCK@0.1 baseline | 0.037138 (41/1,104) | 0.037138 (41/1,104) |

PCK@0.1 by joint (correct / visible; baseline → candidate):

| AP-10K channel | Baseline | Candidate |
|---|---:|---:|
| left_eye | 56/91 (0.6154) | 58/91 (0.6374) |
| right_eye | 53/95 (0.5579) | 55/95 (0.5789) |
| nose | 57/105 (0.5429) | 54/105 (0.5143) |
| neck | 44/99 (0.4444) | 46/99 (0.4646) |
| root_of_tail | 2/57 (0.0351) | 5/57 (0.0877) |
| left_shoulder | 27/67 (0.4030) | 33/67 (0.4925) |
| left_elbow | 29/62 (0.4677) | 26/62 (0.4194) |
| left_front_paw | 27/58 (0.4655) | 23/58 (0.3966) |
| right_shoulder | 26/68 (0.3824) | 29/68 (0.4265) |
| right_elbow | 26/68 (0.3824) | 25/68 (0.3676) |
| right_front_paw | 30/59 (0.5085) | 26/59 (0.4407) |
| left_hip | 11/42 (0.2619) | 11/42 (0.2619) |
| left_knee | 14/42 (0.3333) | 16/42 (0.3810) |
| left_back_paw | 11/40 (0.2750) | 11/40 (0.2750) |
| right_hip | 15/51 (0.2941) | 17/51 (0.3333) |
| right_knee | 22/50 (0.4400) | 22/50 (0.4400) |
| right_back_paw | 20/50 (0.4000) | 19/50 (0.3800) |

The comparable overlays for validation annotation 2482 are in the local cache
at `%USERPROFILE%\.cache\petlens\baseline-val-overlays\val-2482-00.jpg` and
`%USERPROFILE%\.cache\petlens\models\ap10k-minimal-tune-2026-10-25\experiment-986fd1a5-3048-4a4c-a951-494099e85811\overlays\val-2482-00.jpg`.
Visual review shows several predicted points displaced from their red
annotations; aggregate PCK is not evidence that individual landmarks are
reliable. The evaluator reports heatmap peaks, but confidence calibration,
low-confidence rejection, and memory use were not measured in this run.

## Reproducibility and artifacts

- Hardware/runtime: Windows 11; Intel Core Ultra 9 386H CPU; Intel integrated
  graphics present but unavailable to PyTorch; no CUDA. Python 3.12.10,
  PyTorch 2.6.0+cpu, torchvision 0.21.0+cpu, OpenCV 4.10.0.
- Existing baseline duration: 1,205.218 s for 30 epochs. This run: 57.156 s
  for one additional epoch. Candidate checkpoint: 184,693,983 bytes. CPU
  latency is forward-pass-only, not end-to-end video inference.
- Baseline SHA-256:
  `59a25c5cab004c89b3f9fe5afa200bd9b67161aaf6c05e5a99261ceaf95fbf98`.
- Candidate `checkpoint_last.pt` SHA-256:
  `1eaa50cc722de6b99e042e79d9991db83476431c8431ebccadb077e5c2d91c4c`.
- Candidate output, optimizer state, training metrics, metadata, per-instance
  predictions, evaluation JSON/Markdown, and four overlays remain outside the
  repository at `%USERPROFILE%\.cache\petlens\models\ap10k-minimal-tune-2026-10-25\experiment-986fd1a5-3048-4a4c-a951-494099e85811`.
- Reproduced baseline evaluation and candidate training/evaluation with:

  ```powershell
  .venv\Scripts\python.exe training\evaluate_pose.py `
    --checkpoint "$HOME\.cache\petlens\models\ap10k-corrected-2026-10-24\experiment-f15db4ca-667b-48c0-895d-950d8599bbfc\checkpoint_best.pt" `
    --split val --device cpu `
    --dataset-root "$HOME\.cache\petlens\datasets\extracted\ap-10k" `
    --prepared-dir "$HOME\.cache\petlens\datasets\prepared" `
    --metrics-out "$HOME\.cache\petlens\baseline-val-metrics.json"

  .venv\Scripts\python.exe training\train_pose.py `
    --resume "$HOME\.cache\petlens\models\ap10k-corrected-2026-10-24\experiment-f15db4ca-667b-48c0-895d-950d8599bbfc\checkpoint_best.pt" `
    --epochs 31 --device cpu `
    --dataset-root "$HOME\.cache\petlens\datasets\extracted\ap-10k" `
    --prepared-dir "$HOME\.cache\petlens\datasets\prepared" `
    --output-dir "$HOME\.cache\petlens\models\ap10k-minimal-tune-2026-10-25"

  .venv\Scripts\python.exe training\evaluate_pose.py `
    --checkpoint "$HOME\.cache\petlens\models\ap10k-minimal-tune-2026-10-25\experiment-986fd1a5-3048-4a4c-a951-494099e85811\checkpoint_last.pt" `
    --split val --device cpu `
    --dataset-root "$HOME\.cache\petlens\datasets\extracted\ap-10k" `
    --prepared-dir "$HOME\.cache\petlens\datasets\prepared" `
    --metrics-out "$HOME\.cache\petlens\models\ap10k-minimal-tune-2026-10-25\experiment-986fd1a5-3048-4a4c-a951-494099e85811\validation-epoch31.json"
  ```

This one-epoch invocation was explicitly bounded by `--epochs 31`, and the
trainer wrote resumable `checkpoint_last.pt` and validation-selected
`checkpoint_best.pt` in a new directory. The run did not configure a strict
wall-clock, RAM, or disk quota; peak memory was not recorded. Future longer
runs should add or enforce those resource limits before starting.

## Verification and decision

- `training/evaluate_pose.py` baseline reproduction: PASS; model PCK@0.1
  0.425725 vs box-center 0.037138.
- `training/train_pose.py` resumed epoch 31: PASS; validation loss
  0.848593, so checkpoint selection correctly retained epoch 30 as best.
- Candidate validation evaluation: PASS; PCK@0.1 0.431159 vs baseline
  0.425725, but interval overlap, worse validation loss, and joint-level
  regressions mean this is not a sufficiently supported model promotion.
- **Decision:** keep the original epoch-30 checkpoint as the selected
  experimental checkpoint; retain epoch-31 artifacts for traceability only;
  do not copy either artifact into app/API inference or the APK.
- **Not evaluated:** official AP-10K test split, detection, end-to-end
  inference, dog-walking video, temporal stability, gait, clinical outcomes,
  osteoarthritis, confidence calibration, and RAM footprint.

This remains a still-image development experiment. It does not validate
canine walking analysis or clinical use.
