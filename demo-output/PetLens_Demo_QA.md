# PetLens Version 6 demo — QA record

## Export

- File: `PetLens_V6_Demo_30s.mp4`
- Duration: **30.00 seconds**, verified as 900 decoded frames at 30 fps.
- Frame size: **1920 × 1080**, 16:9.
- Video: **H.264/AVC High profile**, `avc1`, progressive `yuv420p`, 30 fps.
- Audio: none; no narration or music was produced.
- Playback: FFmpeg decoded the complete output successfully with exit code 0 and no decode errors. OpenCV independently read all 900 frames.
- Visual review: representative frames from the opening, source clip, API summary, validation scope, each graph, and closing card were inspected; `PetLens_Demo_Assets/qa-contact-sheet.jpg` is the contact sheet. No accidental desktop UI or notification content appears.

## APK provenance

- Local filename: `PetLens_Demo_Assets/PetLens_Version_6.apk`
- Source: [Version 6 EAS artifact](https://expo.dev/artifacts/eas/tRpU5K7Gq-G8MAR2rNCUJEI7ZaAEgEek8QHHVdiLFRg.apk)
- Release record: production APK from commit `1d549d2`, Android `versionCode` 6.
- Size: **114,410,721 bytes**
- SHA-256: `376982B6444A15294C9C15D4CF90EAE4383791FD57F2F4DA30FAE4853161A7DF`
- The APK was **not installed or launched**, and no Version 6 screen recording was captured: this environment has no available Android device, emulator, or `adb`. The APK is a verified release reference, not a claimed video source.

## Genuine fallback footage and API result

- Source file: `PetLens_Demo_Assets/PetLens-motion-api-demo-h264.mp4`, a previously rendered 30-second demo of the actual PetLens production API response and the source research clip.
- The inserted dog footage is the genuine clip attributed in the video to Shin et al., *PLOS ONE* (2013), DOI `10.1371/journal.pone.0059875`.
- The API summary shown is the actual `/api/analyze` response for that clip: `opencv-motion`, 60 decoded frames, 59 motion-trace points, and stride symmetry not measured. This is a motion-only result, not app footage, canine pose inference, a gait result, or clinical analysis.

## Validation graph provenance and consistency

- Source report: `reports/canine-pose-validation/` and `reports/petlens-positive-results/01-validation-vs-baseline.png`.
- The demo uses the report's original PNG graph exports; the complete PNG and SVG graph set, `metrics.json`, and `training.csv` are copied to `PetLens_Validation_Graphs/`.
- PCK@0.1: experimental pose model **470 / 1,104 = 42.6%**; box-center baseline **41 / 1,104 = 3.7%**.
- Evaluation: 110 dog instances from the AP-10K official validation split, using ground-truth dog boxes. The validation split selected the checkpoint; this is development validation, not independent test evidence.
- The experimental pose model is not the production app inference path. The study does not establish walking-video tracking, gait measurements, or clinical performance.
- Prediction-score graph: source is the report's actual validation peak-heatmap-score distribution. Scores are uncalibrated and are not probabilities that a prediction is correct.
- Graphs and on-screen labels preserve the source metrics and caveats; no model landmark overlay is applied to the walking clip.

## Remaining limitation

The requested native Version 6 workflow could not be recorded without an Android device/emulator. This export uses an explicitly labeled, genuine research-video/live-API fallback plus the verified experimental validation charts; it does not claim to show the APK UI.
