# PetLens Version 6 demo — 30-second script

**Format:** 16:9, 1920 × 1080, 30 fps, H.264<br>
**Audio:** No narration or music; all information is on screen.<br>
**App-footage note:** No Version 6 APK screen recording is included. The app could not be launched on an Android device or emulator in this environment. The video labels its genuine research-video and live API fallback rather than presenting it as APK footage.

| Time | Visual | On-screen copy |
|---|---|---|
| 0:00–0:03 | PetLens logo and title card | “PetLens” · “AI-assisted canine movement analysis” · “Version 6 reference build” |
| 0:03–0:09 | Genuine dog-walking research clip, isolated from the earlier live-API demo | “A real walking clip enters the workflow” · “DMD research video” · “Not a canine osteoarthritis or gait-validation dataset” |
| 0:09–0:14 | Summary of the actual production `/api/analyze` response for that clip | “OpenCV whole-picture motion” · “60 decoded frames” · “59 motion-trace points” · “Stride symmetry: Not measured” |
| 0:14–0:17 | Experimental study scope card | “AP-10K dog-only validation” · “110 instances” · “17 landmark types” · “1,104 visible keypoints” · “Ground-truth boxes; development validation, not independent testing” |
| 0:17–0:21 | Actual PCK comparison graph | “42.6% (470/1,104) vs. 3.7% (41/1,104) box-center baseline” · “Not independent test or end-to-end video accuracy” |
| 0:21–0:24 | Actual per-keypoint PCK graph | “PCK@0.1 across 17 AP-10K landmarks” · “Experimental validation; tail-root result remains low” |
| 0:24–0:27 | Actual prediction-score histogram | “Model output strength is not calibrated confidence” · “Peak heatmap scores are not probabilities of correctness” |
| 0:27–0:30 | PetLens close | “From movement video to measurable insights” · “Real-world video tracking, gait validation, and independent testing remain necessary” |

## Narration

None. The demo uses readable captions and contains no audio track.

## Sources shown

- Version 6 APK artifact: `PetLens_Demo_Assets/PetLens_Version_6.apk`. It is included as the release reference, not as captured footage.
- Genuine source video and live API response: `PetLens_Demo_Assets/PetLens-motion-api-demo-h264.mp4`.
- Validation graph exports and metrics: `PetLens_Validation_Graphs/`.
- Research-video attribution: Shin et al., *PLOS ONE* (2013), DOI `10.1371/journal.pone.0059875`.
