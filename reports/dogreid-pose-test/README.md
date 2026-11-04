# DogReID CPU pose smoke test — 2026-11-03

Both candidates are useful for the immediate pose-pipeline goal. Prefer Lurcher #115 for initial debugging: clear body outline and slower motion. Chihuahua mix #198 provides a harder test of overlapping legs, fast steps, dark fur and camera motion. Neither needs to pass strict gait-screening criteria to serve this purpose.

## Results and artifacts

Actual inference completed on 60 consecutive source frames of #115 (about 2 seconds) and 90 of #198 (3 seconds). No frames were interpolated, predictions smoothed, or identities corrected.

| Clip | Median inference | P95 | Total inference | Effective throughput* |
|---|---:|---:|---:|---:|
| #115 | 127 ms/frame | 194 ms | 8.42 s | 7.1 fps |
| #198 | 105 ms/frame | 162 ms | 10.23 s | 8.8 fps |

*Frames / sum of inference times. Timing includes optical-flow box update, pose preprocessing, model execution and decoding of outputs; excludes video decoding, visualization, encoding and startup. This is not full application throughput or a claim of 30 fps. Model/session initialization measured 0.334 s after imports, not cold interpreter startup. First frame included, no warmup excluded.

- [Lurcher overlay MP4](115-overlay.mp4), [frame sheet](115-sheet.jpg), [raw predictions](115-predictions.json).
- [Chihuahua-mix overlay MP4](198-overlay.mp4), [frame sheet](198-sheet.jpg), [raw predictions](198-predictions.json).
- [Measured metrics and model provenance](metrics.json), [execution log](run.log), [reproduction script](run.py).

Overlay: orange denotes model-left and blue model-right; these are anatomical model labels, not screen-side labels. Solid points/segments require raw score >=0.5, open circles indicate lower scores. Raw SimCC scores are not calibrated probabilities and can exceed 1.

## Model and environment

Used the existing 54,478,120-byte RTMPose-m AP-10K ONNX model (256×256 input), SHA256 `1cfd1c86e0d9e5d5f95178bcd95ee9a4e8386a624cd3c57519f27ff58cac7f28`, checked against the earlier local provenance record. Existing isolated Python 3.12 environment, rtmlib, OpenCV and ONNX Runtime; explicit CPUExecutionProvider, two intra-op threads and one inter-op thread. No dependencies installed, models downloaded, or application code changed.

This is the animal-specific AP-10K model, not a human COCO head with renamed channels. The 17 outputs include eyes, nose, neck, tail root, both shoulders/elbows/front paws, and both hips/knees/back paws. It does not supply separate carpal, tarsal/hock or toe joints. Model capability and lightweight deployment are documented in the [rtmlib model table](https://github.com/Tau-J/rtmlib) and [OpenMMLab RTMPose project](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose). The repository's existing application backend warns about a human COCO head; this experiment does not alter or validate that backend.

Source videos remain DogReID-1553 V3.2, CC0-1.0: [DOI](https://doi.org/10.7910/DVN/LVTRLG). Dog IDs, video IDs and video hashes remain in [the screening manifest](../dogreid-1553/screened-videos.json). The CC0 video license is distinct from upstream model/software licensing; model provenance is retained, but no new redistribution licensing audit was performed.

## Tracking stability and failure cases

This is framewise pose estimation with a lightweight crop tracker, **not a validated four-paw identity tracker**. Initialize the box from the dataset first-frame annotation; translate it using median Lucas–Kanade sparse optical flow within the prior box. No automatic learned detector is used in the completed run. Background features can bias this tracker, scale is fixed, and it cannot reacquire a lost dog or resolve multiple dogs. Both short segments retained a usable dog crop in inspected sheets; that is not detector recall.

At raw score >=0.5, per-paw coverage across #115 is 91.7–100%; #198 is 97.8–100%. High scores do not prove correct localization or persistent left/right identity.

Median consecutive paw displacement, normalized by current box diagonal, is 0.010–0.024 for #115 versus 0.037–0.053 for #198. P95 ranges are 0.045–0.122 and 0.090–0.246 respectively. This raw image-space measure combines gait, camera motion, crop behavior and model jitter; it is not a tracking accuracy score. The faster #198 sequence has substantially larger temporal changes.

Visual review of extracted overlays shows useful paw/leg estimates on both dogs. Far-side limbs overlap or collapse toward near-side limbs; some joint segments cut across the silhouette or put an inferred paw away from a clearly visible foot. In #115, grass/soil camouflage and leg overlap produce weaker left-hind coverage. In #198, crossing legs and brisk motion produce larger jumps and uncertain left/right assignments even at high scores. Internal hip/knee estimates have no visible ground-truth landmarks. No manual annotations exist here to quantify pixel error, ID switches or anatomical correctness, so none is claimed.

The model can propose all four paws and major leg joints, and these clips establish a working offline CPU inference path. Reliable physical hind-paw tracking still needs temporal association, explicit occlusion handling and human review; confidence alone is insufficient.

## Approaches stopped and scope

Initially reused the cached RT-DETR + RTMPose experimental detector path. It produced a plausible first-frame overlay, but one observed first frame took 8.75 seconds with default threading. A two-thread pose-session retry observed 2.34 seconds on its first frame; these single-frame figures are not steady-state benchmarks. Foreground runs were terminated with exit 143 before completion, consistent with runner lifetime limits. A detached attempt did not yield usable completion evidence. Rather than continue debugging orchestration or install another detector, switched to supplied boxes plus optical flow; the completed lightweight run finished normally. Earlier partial overlays were overwritten by the successful run.

No training, new dataset search, GPU use or application integration was performed. This bounded smoke test is sufficient for the immediate investigation; it does not require using the full 60–90 minute allowance.

Reproduce from the repository root:

```bash
bash tmp/rtmpose-test/multi-video-evaluation/python-env.sh reports/dogreid-pose-test/run.py
```

The script depends on that existing local environment, evaluation module (AP-10K names), cached ONNX model and screening files; it is an investigation artifact, not yet a standalone production dependency. Next implementation step: retain this animal-specific pose head, accept a supplied dog crop initially, then add detector/reacquisition and paw identity association as separately tested components.
