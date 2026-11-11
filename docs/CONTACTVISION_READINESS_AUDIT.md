PETLENS — CONTACTVISION CANINE MODEL: DATA READINESS AND IMPLEMENTATION PLAN
Audit date: November 11, 2026. Planning only; no model performance claim.

1. EXECUTIVE VERDICT

PARTIALLY.

We can begin the AP-10K temporal feature adapter and data-validation work now. We are not ready to launch a meaningful supervised training/evaluation experiment with the labels currently on disk. The missing prerequisites are independently reviewed contact sequences, trustworthy physical-paw mapping, and a dog-separated pilot cohort. The available data can exercise conversion, alignment, masks and abstention; it cannot establish contact accuracy.

Keep RTMPose-m AP-10K frozen. Keep ContactVision as the primary architectural reference. Its released model already operates on pose coordinates; an image encoder is unnecessary for the first experiment. Reuse its temporal Transformer design, replace the anatomical input projection and contact head, and train canine weights. No concrete compatibility blocker justifies another model search.

The shortest path is: validate existing saved poses -> collect/review a small dog-separated contact pilot with the existing reviewer -> run one bounded pose-only experiment -> compare with the unchanged rule detector. Paw/surface crops are a later extension, triggered by measured failure patterns.

Repository safety, verified before the audit:

- Branch: feature/canine-gait-v2.
- HEAD: ebaba1c28f2cf553ba9f8e3ce99111d7e9547778, “Checkpoint candidate gait events and Dog02 ground evidence,” November 11, 2026.
- Local upstream reference and a successful read-only git ls-remote both returned this exact HEAD for origin/feature/canine-gait-v2. The checkpoint is pushed. No fetch, commit or push was performed.
- Initial tracked modification: architecture.txt. Initial untracked work: PY~, for, import, logs, p; artifacts/petlens-colab-package-verification.json; artifacts/petlens-pilot-results (1).tar.gz; reports/dalmatian-identity-failures-contact-sheet.png; three reports/petlens-*-comparison.jpg / paw-label-check.jpg images; reports/rtmpose-paw-v2-diagnosis/; tests/PetLens_Husky_ScreenRecording_Test.zip. All retained.
- Important files exist: src/petlens_gait/{inference,events,ground,cycles,metrics,integration}.py; training/{gait_event_review,prepare_paw_annotations,blind_paw_annotations}.py; training/canine_keypoint_schema.json; training/paw_annotation_sources.json; the original S003 and Dalmatian videos; saved Dog02/Dalmatian predictions; reports/gait-event-review-v1/ including its export and drafts; reports/dog02-ground-evidence-v1/diagnostic.json; physical-paw annotations; paw-annotation-data-v1/v2; DogReID manifests.
- The pre-existing architecture.txt was copied byte-for-byte to /tmp/petlens-contactvision-audit-20261111T135449Z/architecture.before.txt before replacement. The same directory contains worktree-before.json with hashes of initial modified/untracked files. Only architecture.txt is intentionally replaced in the repository.
- PETLENS_PROGRESS.md records 267 previously passing tests. Those are historical results; this audit did not rerun tests, inference or training. Metadata probing and visual inspection do not establish new model accuracy.

2. EXISTING DATA INVENTORY

Counts must distinguish files, footage, dogs and labeled examples.

There are 17 locally downloaded DogReID clips carrying 17 distinct canonical dog UUIDs. The identity registry describes 1,553 dogs in the full external dataset; it does not mean 1,553 dogs are locally available. Outside DogReID, there are seven working source/subject groups: original165, Dalmatian, Dog02/S003, S004, forest footage, cream-dog footage, and the separate Husky screen-recording package. Cross-group biological identity is not fully registered. In particular, S003/S004 should remain in one conservative publication/provenance group until identities are resolved, and the Husky package must not automatically count as a different dog from other cream-dog footage.

The inventory below covers 25 source/derived candidate video files after excluding exact copies, lossless working copies, overlays and review renders: four historical sources, three additional local media files, one Husky derivative and 17 DogReID MP4s. This is NOT 25 independent recordings or dogs. The two cream-dog media files appear to show the same dog/session and must stay together. A globally verified unique-dog total is unavailable; 24 apparent source/subject groups is an upper working count, not a validated cohort size.

Usability today: zero adjudicated, dog-separated contact-training/evaluation clips. Four historical walking clips can support adapter diagnostics and cautious annotation; two additional DogReID clips are review-only leads. Existing policies keep Dog02 diagnostic/exploratory, outside training and model selection. No DogReID clip is currently training-approved.

Historical/local sources (FPS below is the rate of the available file, not a claim about the original camera sensor):

| Source and local path | Available timing / size | Saved pose coverage | Labels, visibility and permitted use |
| --- | --- | --- | --- |
| original165: 4300700-sd_426_240_30fps.mp4; identical copies under tmp/ | 30000/1001 = 29.97003 FPS; 165 frames; 426x240; 5.505 s container duration | 165 rows, 161 successful pose frames in original165-final-validation/predictions.json | Side view, but the dog and paws occupy few pixels. Existing trajectories/events are algorithmic candidates. Useful conversion/development case; poor primary precise contact-timing or image-crop benchmark. Original acquisition/source rights need provenance. |
| Dalmatian: tests/13792872-hd_1080_1920_30fps (1).mp4 | 30000/1001 FPS; 177 frames; 1080x1920; about 5.9 s | 177 rows, 174 full pose frames in dalmatian-day2-cfr-20261103/predictions.json | Full-resolution source is retained; side view with entry cropping, overlapping far paws, and sidewalk/curb geometry. A reviewed hind-paw localization subset exists. Potential training/development contact clip after contact review and rights confirmation; extensively inspected, unsuitable as a pristine held-out test dog. |
| Dog02 / Shin et al. Movie S3: test/Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s003.ogv | 12 FPS; 60 frames; 960x544; 5 s; integer PTS 0..59 with time base 1/12 | All 60 rows contain all 17 raw points; working dog02-walking.mp4 and conversion mapping retained | Clearer lateral body/ground view, but hind-paw overlap, dark floor, blur and 83.33 ms sampling. Physical A/B labels and non-independent event drafts only. Preserve existing exploratory-only policy; no verified complete strides or exact high-resolution event truth. |
| Shin et al. Movie S4: tests/Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s004.ogv | 12 FPS; 60 frames; 960x544; 5 s; PTS time base 1/12 | All 60 pose rows in wikimedia-s004-cfr-20261103/predictions.json; exact-pixel lossless derivative and source-frame-map available | Lateral walking, intermittently overlapping limbs and blur; no completed contact reference found. Existing preparation explicitly leaves biological dog independence unresolved. Suitable for coarse training/development annotation after mapping, never a fine-timing benchmark or a “healthy reference.” |
| Forest: tmp/petlens-v2-unseen/dog-walking-01.mp4 | 30 FPS in available file; 180 frames; 1920x1080; 6 s | No matching full saved pose sequence located | Inspection of existing preview shows backlighting, grass and approach toward camera obscuring paws. Exclude from first contact pilot and accurate event timing. Native capture provenance/rights unknown. |
| Cream dog: tmp/petlens-v2-unseen/dog-walking-test-01.mp4 | Available file is 60 FPS CFR; 299 frames; 1734x900; 4.983 s | 299 saved rows in test-01-results/predictions.json | Side view on pavement, but related processed footage, original capture rate and commercial rights are unverified. Existing tracker report has only 3.68% hind-paw tracking coverage. Useful stress case; not verified native-60 FPS evaluation. No human contact labels. |
| Related cream dog: tmp/petlens-v2-unseen/petlens-dog-walking-trimmed.mp4 | Nominal 60 FPS, actual average 982/35 = 28.05714 FPS; 982 frames / 35 s; PTS gaps 16.67..100 ms | No matching full pose sequence located | Appears same dog/session as preceding clip. Variable sampling and uncertain source transformations: exclude native gait-timing evaluation. Do not count as another dog. |
| Husky: tmp/petlens-husky-evaluation/PetLens_Husky_Evaluation/husky_screenrecord_clean.mp4 | Screen recording derivative; nominal 60, average 3200/363 = 8.81543 FPS; 63 decoded frames; PTS gaps 17..400 ms; 1228x754 | 63 raw pose rows; 20-frame blind localization manifest/template | Explicitly EXCLUDED from native gait-timing validation. Container nb_frames says 64, while ffprobe decodes 63 and the preparation/predictions contain 63. Capture timing is not canine motion timing. Original screen recording is unavailable. Retain exploratory localization only; no verified gait contact sequence. |

Prediction directories in the table are beneath tmp/rtmpose-test/multi-video-evaluation/runs/ unless another prefix is shown. Husky predictions are in tmp/petlens-husky-evaluation/husky-inference/.

Local DogReID recordings, all under reports/dogreid-1553/videos/. Every row is one different supplied dog UUID. All have training_approved=false and PetLens split unassigned. FPS is the distributed MP4 rate; original handset capture history is not independently attested.

| Clip | FPS / frames | Existing screen decision and obstacle |
| --- | --- | --- |
| 017 | 29.97003 / 475 | Reject: overhead, sniffing, leaves, camera motion and cropping. |
| 053 | 29.97003 / 220 | Reject: steep downward view and major roll on sand. |
| 056 | 29.97003 / 247 | Reject: sniffing/stops, overhead view, hindquarters cropped. |
| 078 | 29.97003 / 324 | Reject: brief steps/turns, snow and fur obscure feet. |
| 082 | 29.97003 / 872 | Reject: snow play/jumps, leaves frame. |
| 083 | 30 / 234 | Reject: overhead, hindquarter cropping and stopping. |
| 086 | 359/12 = 29.91667 / 149 | Reject: rear/overhead view, fur and sitting. |
| 092 | 30 / 99 | Reject: distant running/rolling on grass. |
| 106 | VFR; nominal 60, average 7590/169 = 44.91124 / 506 | Reject: mostly standing/brief shifts; PTS gaps 16.67..33.33 ms. Average FPS must not replace PTS. |
| 115 | 29.97003 / 85 | REVIEW ONLY: 0..2.8 s slow-walking lead, elevated oblique angle, mottled surface and unclear far hind paw. |
| 122 | 30 / 301 | Reject: toy play, turning, camera tilt/cropping. |
| 140 | 30 / 452 | Reject: standing, no sustained walking. |
| 170 | 30 / 237 | Reject: mostly rear view, sniffing and stops. |
| 180 | 29.97003 / 430 | Reject: distant ball play/running and camera motion. |
| 182 | 30 / 171 | Reject: lying/rolling, grass hides paws. |
| 195 | 29.97003 / 56 | Reject: too short and oblique, then stops. |
| 198 | 30 / 388 | REVIEW ONLY: inspect 0..4.5 s; possible walk/brisk trot, elevated tracking view and far-paw overlap. Exclude later curb, second dog and blur. |

Only partial saved pose sequences exist for these leads: reports/dogreid-pose-verification/115-predictions.json has frames 0..59 (60 of 85); 198-predictions.json has frames 0..89 (90 of 388). The earlier dogreid-pose-test directory contains another pose pass, not additional dogs or videos. The verification pass used the dataset's first-frame dog box plus optical-flow translation, not the standard learned detector. Keep that input-box provenance when mixing inputs. Full-sequence predictions would eventually be needed outside these existing portions; none were generated here.

Timing confidence and alignment:

- Read-only ffprobe inspection found strictly increasing presentation timestamps in every listed available file. Historical original165/Dalmatian have regular 33.37 ms steps; S003/S004 have regular 83.33 ms steps. DogReID is regular at the listed rate except #106. Monotonic PTS validates the encoded timeline, not original camera FPS, unedited acquisition, physical contact, or absence of screen resampling.
- The gait-event frame manifest binds original Dalmatian and S003 frames to integer PTS, time base, source hash and decoded pixel hash. Dog02's conversion file binds original/working timestamps. S004 has its own preserved original frame map and recorded exact decoded-pixel agreement. Reuse these; never obtain timing from a slow review render or annotated playback FPS.
- For Dalmatian, use original PTS. reports/gait-event-review-v1/dalmatian-decoder-diagnosis.json records the earlier decoder issue; do not substitute the earlier unreliable timestamp path. Validate the lossless derivative's index/time mapping against the original before joining poses.
- Matching DogReID pose timestamps to distributed-file PTS is feasible for the saved initial portions, but they lack the same complete original-frame hash chain as the gait manifest. Treat as conditional inputs until a source-bound manifest is verified.

What the annotations actually contain:

- training/paw_annotation_sources.json links original physical hind-paw A/B exports, frame/video/prediction hashes and train/exploratory group policies. Paw-coordinate labels are not contact labels.
- paw-annotation-data-v2/export-summary.json records 42 Dalmatian annotated frames and 79 human-confirmed anatomical hind-paw points (40 right, 39 left). Earlier v1 includes 46 Dalmatian selected frames and 29 merged Dog02 frames, with visible/occluded/unmarked statuses. Do not reinterpret v=0, an absent coordinate, or an inferred AP-10K location as airborne.
- The Dalmatian anatomical mapping is based on reviewer-provided confirmation and prior model investigation, not an independently verified contact-timing reference. Dog02 physical A/B identities do not establish anatomical left/right mapping. Existing predicted association paths are hypotheses, not human-confirmed identities.
- There is one saved gait review ZIP: reports/gait-event-review-v1/reviews/review-d684d28c840a475ba7833f1c045d2504.zip. It is unadjudicated and reports zero complete strides, with 113 unreviewed paw-frames. Although its original independence field says true, later explicit exposure information supersedes that declaration for evidence assessment. Preserve the file unchanged.
- The corresponding written-observation draft records prior exposure, A19 contact, A56 airborne/possible lift-off at 55, B23 airborne, and possible B touchdown within 52..59. These are sparse, qualified human reports, not complete support intervals. Missing last-definite support boundaries remain null. Do not finalize, fill between them, or use them for independent evaluation.
- No independently adjudicated dense contacting/airborne sequence, forepaw contact review, or complete gait test set was found. Browser-only drafts were not inspected; their existence/content cannot be inferred from server files. Blind templates/manifests are infrastructure, not completed independent labels.
- Ground pilot summary remains: 60 source frames, 59 reliable ground registrations, 52 physical-paw motion measurements from saved associations, ZERO usable clearance observations, all 120 hind-paw observations UNKNOWN, zero candidate events/sequences. Ground-region overlap is not clearance and these observations are not training negatives. Evidence: reports/dog02-ground-evidence-v1/diagnostic.json.

Initial-training candidates, after human review and rights checks: selected Dalmatian intervals, S004 at coarse timing, and the already-predicted portions of DogReID #115/#198 if visible identity/contact is assessable. These could reduce new annotation effort but cannot alone supply an adequate clean dog-level test. Original165 is a low-resolution diagnostic. Dog02 retains its exploratory-only exclusion. The Husky, forest clip, uncertain-60 FPS material, and rejected DogReID recordings are unsuitable for accurate first-pilot gait-event timing evaluation.

3. CONTACTVISION REUSE PLAN

Official source inspected on this audit date: [ContactVision repository and README](https://github.com/DaeeYong/ContactVision). It is marked work in progress, with fuller release targeted for December 2026. Do not make the November 30 prototype depend on that future release. Public Python source is enough to use the architecture now; a complete reproducible training pipeline was not verified.

Verified human input/preprocessing:

- OpenPose BODY_25 supplies (T,25,3) x/y/confidence. Selected indices [8,9,10,11,12,13,14,19,20,21,22,23,24] are mid-hip, bilateral hips/knees/ankles, and bilateral big-toe/small-toe/heel landmarks, yielding (T,13,3), flattened to 39 channels.
- Coordinates are pelvis-relative pixel offsets. No body-length scale normalization is present in the inspected preprocessor. Confidence >0.3 controls validity. It interpolates internal gaps up to three frames, extends endpoints, and returns a mask. The command saves only processed coordinates/confidences and discards that mask; entirely missing/long-gap data can remain unsupported. Do not copy this missingness policy into PetLens. [Official preprocessing source](https://raw.githubusercontent.com/DaeeYong/ContactVision/main/scripts/preprocess.py)

Verified network:

FootContactTransformer maps input_dim -> embed_dim with a linear projection, adds a learned positional table of shape (1,10000,embed_dim), applies dropout and stacked PyTorch TransformerEncoder layers, then a linear embed_dim -> 4 classifier. It returns framewise logits (B,T,4). Attention is bidirectional; there is no causal or padding mask in its forward method. Constructor parameters expose embedding width, attention heads, feed-forward width, layer count and dropout. This is a directly reusable temporal design, with no image-feature backbone. [Official model source](https://raw.githubusercontent.com/DaeeYong/ContactVision/main/src/model.py)

Verified inference/output:

The loader expects checkpoint hyperparams plus model_state. It reads the architecture sizes from hyperparams; their actual checkpoint values were not inspected because no checkpoint was downloaded or loaded. Inference uses nonoverlapping 128-frame chunks, zero-pads the last chunk without an attention mask, applies sigmoid and thresholds at 0.5, then trims padding. Thus 128 is the released inference setting, not a demonstrated mandatory training length. The four outputs mean left toe, right toe, left heel, right heel. There is no unknown state, probability export or event decoder in that path. The CLI's parsed model-path argument is not used in its main loader call. Reuse the formulation and model component rather than this CLI unchanged. [Official inference source](https://raw.githubusercontent.com/DaeeYong/ContactVision/main/scripts/inference.py)

The paper describes supervised contact labels derived from mocap through estimated ground reaction forces, with pressure-mat validation. Those are human results, not canine labels or measured canine performance. Exact original loss, optimizer, training window policy and missing-label treatment could not be verified from the accessible released training material; do not invent them. PetLens's explicit choices below are adaptations. [Official publication](https://doi.org/10.1111/cgf.70334)

Canine adaptation:

| Component | Decision |
| --- | --- |
| RTMPose-m AP-10K | Retain and freeze; consume saved outputs first. |
| Human BODY_25 converter | Replace with AP-10K adapter; no OpenPose runtime. |
| Human 13-joint anatomy | Replace with all 17 existing AP-10K channels in their recorded order. |
| Human pelvis reference | Replace with midpoint of neck and tail-root, divided by their observed distance. This is a projected body reference, not canine pelvic/ground geometry. |
| Input projection | New 69-channel projection: 17 x (relative x, relative y, rawScore, observed mask) + elapsed seconds since previous source frame. |
| Temporal network | Reuse Transformer encoder organization, positional mechanism, dropout and per-frame classification pattern. Add a frame-padding attention mask. |
| Human classifier | Replace/reinitialize all weights and biases, despite both tasks having four outputs. New order LF, RF, LH, RH; no human-to-paw output correspondence. |
| Targets | Independently reviewed visual contact=1, airborne=0; all other states have target-valid mask=0 and preserved reason. |
| Probabilities | Sigmoid of each paw logit; these are estimates requiring evaluation/calibration, not RTMPose raw scores. |
| Unknown/unassessable | Explicit abstention outside binary classifier: bad timing/reference, unresolved identity, missing/occluded evidence or probability ambiguity. Not a fifth contact channel and not airborne. |
| Events | Candidate airborne->contact touchdown and contact->airborne lift-off within a continuous verified identity segment. Unknowns break event decoding; never connect across them. |

AP-10K order is defined in training/canine_keypoint_schema.json: eyes, nose, neck, root_of_tail, left shoulder/elbow/front paw, right shoulder/elbow/front paw, left hip/knee/back paw, right hip/knee/back paw. Paw indices are 7,10,13,16. AP-10K does not supply toe/heel pairs, paw pads, a support polygon or a measured ground plane. Its “hip”/“knee” labels for digitigrade animals have the documented knee/ankle interpretation; do not derive anatomical hip angles or invent canine landmarks.

Reuse of saved RTMPose outputs:

Yes, the saved raw x/y/rawScore sequences supply pose-only training features after conversion. They are not directly compatible with the human 39-channel tensor or pretrained input projection. Name-based schema validation, source joins, body normalization and masks are the minimum conversion. Existing normalized-paws.csv files cover selected hind-paw channels and eligibility rules; they are useful diagnostics, not complete 17-channel temporal training datasets.

Measured rawScore ranges from the saved files:

| Saved sequence | All-keypoint minimum..maximum | Paw-only minimum..maximum |
| --- | --- | --- |
| Dog02 | 0.485909..1.464501 | 0.485909..1.442982 |
| Dalmatian | 0.132612..1.497155 | 0.186339..1.497155 |
| original165 | 0.410000..1.536400 | 0.410000..1.481700 |
| S004 | 0.700904..1.570708 | Not separately aggregated in this audit |
| Husky | 0.708360..1.766423 | 0.709973..1.498634 |
| DogReID #115 verification | 0.150413..1.455884 | 0.429229..1.287802 |
| DogReID #198 verification | 0.431587..1.373369 | 0.431587..1.360297 |
| cream-dog test01 | 0.518734..1.544587 | Not separately aggregated in this audit |

These are uncalibrated model responses. Dog02 has 725 of 1,020 scores above 1. Preserve rawScore exactly, including values above 1. Never silently clip, relabel as poseConfidence, or route it through the rule detector's [0,1] confidence contract. A neural feature may use the raw finite number directly; any later standardization must be explicit, fitted only on training dogs and stored with the model. The detector's conservative abstentions remain unchanged.

A raw AP-10K left/right output is a model channel, not proof of physical identity. A finite/high-score point may also be hallucinated behind another limb. Keep model-channel features separate from reviewed physical-paw mapping and continuity. Supervision requires a supported mapping to LF/RF/LH/RH; unmapped A/B records cannot be guessed or assigned by proximity to make training work. Current human mappings may validate selected hind frames, not the entire sequence or forepaws. Keep missing-keypoint, score-eligibility, human visibility, identity-continuity and label-valid masks distinct.

For the first adapter, use the existing neck>=0.70 / tail-root>=0.80 raw-response eligibility and a finite positive neck-tail scale, with a fixed generic point threshold of 0.50. These are explicit feature-eligibility rules, not calibrated probabilities or contact rules. Freeze them across clips. Keep all finite raw points/scores in provenance even when their normalized feature is masked. Missing normalized x/y become zero only alongside mask=0; a genuine normalized zero remains distinguishable through mask=1. Do not interpolate missing paws or extend endpoint identities. Missing body reference invalidates that frame's feature use and splits eligible runs.

Sequence sampling: preserve original frame indices, integer PTS/time base and timestamps, including failures. No time resampling for the first experiment. Use actual delta-seconds and split on source changes, identity breaks, missing body reference or discontinuities. A 128-frame window is 2.13 s at 60 FPS, 4.27 s at 30 FPS and 10.67 s at 12 FPS; these are not equivalent contexts. Keep 12 FPS historical material outside the first native-60 FPS measured pilot. Pad short valid runs with an explicit attention mask and mask padded loss. For offline inference later, overlap windows and fuse logits at the original frame timestamps; do not inherit artificial 128-frame boundary jumps. Reject all-padding windows. Do not oversample low-FPS footage to manufacture event precision.

Training requirements, proposed rather than attributed to unreleased upstream code:

Use masked BCEWithLogitsLoss, summed over valid contacting/airborne paw-frames and divided by their count. Unknown, unreviewed, uncertain, occluded, unassessable, unresolved-identity and padded targets have zero loss weight, never negative labels. Skip batches/windows with zero supervised elements. Compute any class weighting only from training dogs. Missing pose is an input-quality condition, separate from human contact state; for this conservative pilot do not score or train a paw-frame whose identity/paw observation cannot support the feature contract. Report the excluded coverage. No rule-generated events or pseudo-labels initialize human targets.

Split before extracting windows. Every source clip, crop, derivative and augmentation inherits one canonical dog key and one split. Keep unresolved same-dog/publication groups together; hashes catch duplicate files but cannot establish different dogs. No evaluation-dog frames in training, normalization, threshold selection, model selection or pretext training. Validation dogs may select a checkpoint; test dogs remain locked until one final evaluation. Inspecting pose outputs does not automatically invalidate future independently blind contact annotations, but existing data-driven algorithm decisions make these historical dogs development cases.

Weights and commercial position:

- ContactVision code is MIT with copyright/permission notice retention. Commercial code adaptation is permitted under those terms. [Official license](https://raw.githubusercontent.com/DaeeYong/ContactVision/main/LICENSE)
- The README lists checkpoints/best_model.pth, but no checkpoint-specific rights/provenance statement or full training-data permission chain was verified. The repository-wide MIT notice is positive evidence, not independent clearance of third-party training inputs. No checkpoint bytes were inspected. Original training-data rights and whether a separate weight grant applies remain unresolved; scratch canine training avoids depending on those human weights.
- If later cleared, shape-compatible Transformer attention/feed-forward/LayerNorm layers could initialize temporal layers. Input projection must be new; all four classifier outputs must be new. Initially reset positional embeddings because time scale and window sampling differ. Fine-tune all reused temporal layers on dogs. Shape compatibility does not imply useful cross-species dynamics; test this claim.
- OpenPose is not required when consuming RTMPose outputs. Its default license is noncommercial; do not import that runtime into PetLens. [OpenPose terms](https://raw.githubusercontent.com/CMU-Perceptual-Computing-Lab/openpose/master/LICENSE)
- MMPose code is Apache-2.0; the AP-10K dataset publishes CC BY 4.0. These do not independently document every existing ONNX checkpoint/export and source-image right. Keep the current RTMPose checkpoint hash/provenance and dependency notices; complete its artifact rights record before commercial distribution. The adapter needs neither new weights nor new dependencies. [MMPose license](https://raw.githubusercontent.com/open-mmlab/mmpose/main/LICENSE), [AP-10K license](https://raw.githubusercontent.com/AlexTheBad/AP-10K/main/LICENSE)

Later visual evidence extension — defer until pose-only results exist:

Paw-plus-surface crops could reveal toe/pad-ground separation, visible settling/deformation, shadows, surface texture, partial overlap and whether a predicted paw belongs to the intended limb. They may distinguish geometrically similar poses with different visible contact. They cannot prove force-bearing contact or recover an invisible boundary.

Use original-source frame indices/PTS, raw image-space paw locations and the same body-scale reference to define a crop containing the distal limb and adjacent surface. Preserve crop-to-source transform, source pixel hash, padding/out-of-frame fraction, scale and identity quality. An uncertain center produces a flagged/unusable crop, not an invented location. Short aligned crop sequences plus a wider body context may later reduce identity ambiguity. No per-video crop tuning.

Dalmatian and DogReID have enough image resolution to inspect this possibility, although visible paw pixels, blur, oblique views and overlap matter more than nominal frame dimensions. S003/S004 provide some visual surface evidence but remain limited by compression and 12 FPS. original165 has too few paw pixels for a strong appearance benchmark. Husky screen sampling and uncertain-source 60 FPS clips remain timing-ineligible even if their crops look sharp.

Additional inputs would be the rights-cleared original frames/crops, transform/quality metadata, the same independent per-paw contact labels, visibility/identity masks and enough variation in coats/surfaces to avoid shortcuts. Add an image encoder/fusion branch only if measured pose-only errors concentrate on visually resolvable ambiguities. Do not build it for the first training proof of concept.

4. DATASET OPPORTUNITIES

No audited source provides a verified commercially cleared canine touchdown/lift-off benchmark ready to plug into training. This is a scoped finding from these sources, not a claim that none exists anywhere. No dataset was downloaded during this audit.

A = actual contact-related annotation; B = pose data without verified temporal contact labels; C = video without contact labels. An image contact mask or algorithmic phase estimate is not a force-verified event sequence.

| Source / class | Verified supervision and timing | Commercial suitability and decision |
| --- | --- | --- |
| BITE dog ground-contact annotation — A, static | Human annotations of flat ground and dog mesh ground-contact points, described in the paper. Not an ordered per-paw touchdown/lift-off sequence. Could inform static contact supervision only. | Official release covers data, models and software under noncommercial research terms; commercial training/use needs agreement. Exclude from immediate PetLens training, including teacher/pseudo-label use. [Paper](https://openaccess.thecvf.com/content/CVPR2023/papers/Ruegg_BITE_Beyond_Priors_for_Improved_Three-D_Dog_Pose_Estimation_CVPR_2023_paper.pdf), [license](https://raw.githubusercontent.com/runa91/bite_release/master/LICENSE) |
| DLC_Horse equine dataset — B; phase task described, A release unverified | Official README describes stereo 15 FPS footage, body landmarks and hoof stance/swing/occluded detection. A directly reusable timestamped contact-label export and independent event reference were not verified. Species/domain conversion remains necessary. | No commercial dataset license verified in the public repository. Do not assume README citation language grants reuse. No first-pilot dependency. [Official dataset](https://github.com/NarimanNiknejad/DLC_Horse), [documentation](https://raw.githubusercontent.com/NarimanNiknejad/DLC_Horse/main/README.md) |
| AP-10K — B | Still-image 17-joint animal pose. No contact/airborne sequences, event times or dependable dog-level temporal grouping. Already represented in PetLens's pose pipeline. | Published CC BY 4.0 with attribution obligations; source-image rights remain relevant. No contact annotation savings, no new backbone work. [Official dataset](https://github.com/AlexTheBad/AP-10K), [license](https://raw.githubusercontent.com/AlexTheBad/AP-10K/main/LICENSE) |
| RGBD-Dog — B | Official release describes five dogs, multiview HD RGB at 59.97 FPS, mocap/timecodes and lower-rate Kinect data. Documented BVH neutral-frame offset requires alignment. No released true contact-event labels verified. Potential future annotation footage. | Available for academic use; companies are directed to request terms. Commercial permission unresolved. Do not delay pilot for access/negotiation. [Official release](https://github.com/CAMERA-Bath/RGBD-Dog/blob/master/README.md) |
| DogMo — B | 1,200 sequences, 10 dogs, five synchronized RGB-D cameras, 15 FPS, masks/keypoints and action labels. No true contact/event-label release verified. Foot-skating evaluation does not establish contact ground truth. | Project website's CC BY-SA notice applies to website content; commercial dataset/checkpoint rights were not verified. Do not treat it as a commercial data grant. [Paper](https://arxiv.org/html/2510.24117v1), [project](https://pie-lab.cn/DogMo/) |
| InterPet4D — B | Time-aligned multimodal dog interactions and pet motion/SMAL fits. No verified paw-ground touchdown/lift-off sequence in the audited card. | Dataset card is CC BY-NC 4.0. Exclude commercial pilot without separate permission. [Official dataset card](https://huggingface.co/datasets/ohicarip/interpet4d) |
| DogReID-1553 — C, strongest already-local reuse option | 7,463 published videos / 1,553 dog IDs; first-frame boxes and identity grouping, no contact labels. Authors describe conversion/trimming of submitted videos, so original capture rate is not guaranteed by file FPS. Locally, only #115/#198 survived as review leads. | Official Dataverse release states CC0 1.0 and that contributors agreed to it. Commercial reuse is permitted under the published dedication; preserve provenance and apply content-specific rights handling. This saves sourcing/identity bookkeeping, not contact labeling. [Official release and terms](https://doi.org/10.7910/DVN/LVTRLG) |
| Shin et al. PLOS supplemental videos — C | Existing S003/S004 have 12 FPS original available OGV timelines; no aligned paw contact-event export was found. Paper's laboratory measurements do not label every supplemental-video paw frame. | Embedded tags record CC BY 3.0; S004 Commons description lists CC BY 2.5. Both allow commercial reuse with attribution, but retain the discrepancy and original metadata. Use original publication provenance and record derivatives. Reuse files already present; no new download. [Publication/supporting information](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0059875), [S004 source description](https://commons.wikimedia.org/wiki/File:Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s004.ogv) |

Immediate choice: reuse the existing reviewed geometry and #115/#198 portions where useful, while recording a small set of clear, rights-cleared native videos. Do not wait for restricted datasets or convert public poses into fabricated contact targets.

5. PILOT TRAINING PLAN

Minimum practical pilot recommendation: eight verified dogs, two usable 8..12-second clips per dog, 16 clips total. This is an engineering pilot size, not a demonstrated sample-complexity guarantee or a market-readiness benchmark. Reserve four dogs/eight clips for training, two dogs/four clips for validation, two dogs/four clips for locked test. Keep all clips of a dog together. Existing clean, rights-cleared, independently reviewed footage may substitute; it cannot reduce the number of verified dog groups or relax timing requirements. Dog02 remains excluded from training/model selection under its existing policy.

Start by reviewing two short candidate clips from different training dogs to confirm that contact boundaries can be judged before annotating the remainder. This is an annotation gate inside the same pilot, not another model experiment. Historical 12 FPS cases may exercise the adapter but do not replace the native-rate pilot. Eight dogs can expose gross failure to generalize; it cannot support broad product accuracy claims.

Capture: prefer native 60 FPS, minimum 1080p with short exposure and enough light. Native 120 FPS is useful only if already convenient; never upsample. Use a stable lateral camera near lower-body height with a slight oblique offset if needed to separate far limbs, full body and walking surface visible, minimal perspective change, no speed changes or turns in the scored interval. Flat firm matte surface, contrasting paws, handler outside the limb view. Record walks in both directions so near/far paws alternate; include different sizes/coats across dogs. Keep first pilot to walking. Require several complete visible stance/swing cycles for each assessable paw across the two clips. Persistent far-paw occlusion is a missing target, never an instruction to infer it.

Annotation process using existing infrastructure:

1. Reuse training/gait_event_review.py, its frame manifest, observation schema, original-frame canvas and ZIP exports. Preserve native PTS, frame/pixel hashes, reviewer ID, exposure declaration, paw descriptions, visibility, continuity, supportState and the six existing stride bracket fields. Do not create another UI.
2. The current reviewer supports two physical paws A/B, not four anatomical paws. For four-output training, use separate fore-pair and hind-pair A/B review exports per clip, with explicit pair/anatomical mapping in descriptions and the conversion job metadata. Save each export before starting the other pair and do not merge browser drafts implicitly. Reuse import/export to keep separate passes; the adapter must reject an ambiguous pair mapping. New source selection belongs in the existing reviewer configuration later, not a second annotation platform.
3. Reviewers independently watch originals with pose overlays, candidate events, prior labels and each other's work hidden. Prior exposure must be declared honestly; exposed drafts are development material and cannot become independent merely by changing a flag. Reviewer 2 must independently assess the scored interval, not only approve reviewer 1's chosen events, so missed-event bias remains measurable.
4. Work by short continuous intervals: identify the physical paw once, mark definite contacting/airborne spans and uncertain/occluded breaks, then inspect transition neighborhoods frame by frame. Use existing support-state fields per source frame; any transcription of a reviewer-declared span is explicit and checked. No filling unreviewed interiors from a few endpoint clicks or from model speed.
5. Touchdown bracket = last definitely airborne to first definitely contacting; lift-off bracket = last definitely contacting to first definitely airborne. Preserve both source frame/time boundaries. A broad “somewhere in frames 52..59” note is not a definite bracket. A stride requires the next same-paw touchdown and continuous reviewed evidence. Use the existing six-boundary structure; uncertain windows may remain in notes as currently supported.
6. Reconcile only after both exports are saved. Preserve original judgments and record adjudication separately through the existing structured files/process. Disagreement, blur, loss of identity and occlusion retain UNKNOWN/uncertain with a reason; never average them into a new definite frame. Complete-stride validation remains strict.

Effort control: reuse existing paw coordinates/mapping as development metadata rather than re-clicking every point; contact reviewers assess support directly from originals. Most effort should go to clear continuous support intervals and event brackets, not repeated pose localization. Do not prepopulate the blind labels with old coordinate overlays or algorithmic contact suggestions. If the existing A/B workflow makes four paws slow, annotate usable near-side paws first across both travel directions, leaving the other targets masked; require all four output types to have training supervision and assessable held-out examples before describing the result as a four-paw classifier.

One training experiment:

- Frozen RTMPose; unchanged rule detector; one ContactVision-style pose-only Transformer. For a small scratch model use embed_dim=64, four heads, ff_dim=128, two encoder layers and dropout=0.1; these are PetLens pilot settings, not claimed upstream hyperparameters. Input width 69; four freshly initialized paw logits; learned position table limited to the 128-frame window. Add frame-padding mask and masked BCE described above.
- Use native pilot poses and source-aligned 128-frame windows with stride 64. Keep all windows/derivatives in their dog's split. Batch/sample dogs rather than letting a long clip dominate. Overlapping windows are correlated examples, not more independent dogs. First proof is offline with future context; no real-time latency claim.
- AdamW, learning rate 1e-3, weight decay 1e-4, max 50 epochs, early stopping after eight epochs without validation masked-BCE improvement. Three fixed random seeds, one configuration, no individual-video tuning. Fit optional positive class weights from training only. Choose the checkpoint from validation loss; do not revisit test dogs.
- Use one fixed initial state decoder: contact probability >=0.65, airborne <=0.35, intermediate UNKNOWN. Require two consecutive eligible samples for a supported run and mark its first eligible sample as the candidate state start. Change of supported run gives a candidate event bracket; an intervening UNKNOWN/identity break resets the sequence and prevents a guessed transition. Freeze this decoder for both neural initialization arms; no per-dog thresholds. Record boundary sensitivity and coverage rather than hiding short phases missed by this rule.
- The original ground-relative rule state machine remains the baseline, using only its actual available independent evidence. If usable clearance is absent it abstains, as on Dog02. Compare paired results on the same source intervals; state that this baseline lacks evidence where appropriate. Do not invent clearance, weaken its gates or feed the learned contact output into it to manufacture a stronger baseline.

Human-pretrained temporal initialization is an optional paired initialization arm of this same experiment, only after checkpoint rights and actual hyperparameters are verified. Match both arms to the exact same feasible architecture/compute budget, reuse only compatible Transformer attention/feed-forward/LayerNorm tensors, reset input/head/positions, and fine-tune on identical canine windows/seeds. If the checkpoint architecture differs from the small proposed model, do not partially load arbitrary mismatches or introduce a second architecture comparison; either use its exact affordable architecture in BOTH arms or defer transfer and run the small scratch arm. Compare validation metrics across the three seeds, choose by a predeclared rule, then evaluate locked test once. If rights or size remain unresolved, report transfer as not tested; it must not delay scratch training or trigger a weight download during this audit.

Evaluation on independently reviewed held-out canine intervals:

- Frame accuracy and balanced accuracy/contact F1 on adjudicated known states, with confusion matrix and per-paw/per-dog counts. Report selective accuracy on accepted predictions separately from correct-and-covered / all eligible known frames so abstention cannot inflate success. Also report probability Brier score on known states.
- Match touchdown/lift-off events one-to-one by type and physical paw within each continuous segment. Never remap test paw identities using the ground truth to maximize accuracy. Use independently adjudicated anatomical mapping; otherwise exclude from anatomical scoring and report the exclusion.
- Predeclare event match tolerance as 50 ms around the reviewed bracket for the native-rate pilot. Use maximum-cardinality/minimum-error matching; one detection cannot explain two reference events. Report precision/recall/F1, missed reference events, unmatched false/duplicate events, and false events per reviewed minute. Missing predicted events due to abstention remain missed in the all-reference recall denominator.
- For matches, report signed timing bias, median/mean absolute error and 95th percentile in milliseconds and source frames. Report zero distance when a prediction falls within the human bracket, distance to the nearest bracket endpoint otherwise, plus bracket width and midpoint-error diagnostics. Wide human brackets are uncertain evidence, not automatic timing successes; define precise-timing subset as brackets <=2 native frame intervals and report exclusions separately. Timing errors concern matched events only and must accompany recall.
- Report annotation coverage, pose eligibility, identity eligibility, prediction coverage, abstained paw-frames and abstention reasons, broken segments and full-stride coverage. Separate near/far paws, frame-rate/source strata and four output channels. Unreviewed regions cannot count as true negatives or false events; report them as unevaluable duration.
- The current conservative rule detector operates on hind paws. Publish paired hind-paw baseline/model metrics; report forepaw classifier metrics separately with baseline “not available.” Do not imply an existing four-paw baseline. Include dog-level results; frames/windows are not independent replicates and two test dogs provide only a preliminary generalization check.

Stopping rule:

Before training, stop the pilot-data expansion for correction if the two-clip annotation gate cannot yield at least three adjudicated complete strides across two dogs, or reviewers cannot give consistent narrow support brackets on clearly visible paws. Preserve uncertain observations and improve recording conditions instead of forcing labels. Before launching the full four-output run, require both contact classes and event types across all four paw channels in training, and assessable examples on validation/test dogs.

For modeling, cap work at the single configuration, three seeds, 50 epochs/patience eight, and two engineering days after validated pilot tensors are available. No weekly tuning on old videos. Use majority-state prediction as a trivial diagnostic alongside the rule baseline. If validation balanced accuracy does not exceed 0.60, event F1 does not exceed 0.60 on the independently reviewed evaluable intervals, or coverage is below 50% of known paw-frames, classify the experiment as insufficient and inspect one aggregate error breakdown: annotation disagreement, pose/identity quality, domain variation or unresolved visual ambiguity. These are pilot decision thresholds, not measured achievements. A pass is only evidence to enlarge the pilot, never a competitive-product accuracy claim. Do not keep the test set open for retries. Any transfer gain must be measured across paired seeds at matched coverage; otherwise report inconclusive.

Schedule judgment:

By November 30, a functional Motion Studio prototype can retain RTMPose, source-aligned playback, the rule baseline, explicit uncertainty, and a small offline learned-contact demo only if labels and evaluation pass the gates. Do not promise a validated four-paw model merely because the adapter is finished. Aim to finish the adapter in roughly 1..2 engineering days, then prioritize pilot recording/review; its elapsed time depends on access to dogs/reviewers. For February–March 2027, scale the same pipeline to more independently sourced dogs, surfaces, cameras and conditions, with a fresh locked benchmark. Add crops only when measured errors justify them. This pilot alone does not substantiate market competitiveness or diagnostic claims.

6. NEXT CODING TASK

Implement ONE “saved AP-10K temporal feature adapter and readiness validator.” Do not implement the neural model, trainer, image branch, event decoder or UI in this task. No implementation was started in this audit.

Exact proposed new files:

- src/petlens_gait/contact_features.py — pure conversion/validation helpers, versioned feature contract, body-relative normalization, distinct masks, contiguous eligible segments and deterministic 128-frame window indexing.
- training/prepare_contact_sequences.py — offline CLI that joins existing saved predictions, original-frame metadata and optional structured review exports, emits auditable feature artifacts and a readiness report. No torch, model loading, inference or network calls.
- tests/test_contact_features.py — meaningful contract and leakage tests with small synthetic inputs, plus read-only fixtures using existing Dog02/Dalmatian data where appropriate. No fixture annotation modifications.

No existing source/annotation file needs modification for this step. Define the contract in module/CLI documentation. A future trainer consumes this output; do not introduce a parallel dataset platform.

Inputs:

1. Existing AP-10K prediction JSON, keypoint schema and associated source metadata. Primary supported input is the versioned dictionary envelope used by training/prepare_paw_annotations.py. Legacy DogReID list-only predictions require an explicit metadata wrapper in the CLI job; no guessing video/model identity from filenames.
2. Existing original frame manifest or verified source-frame-map and a supplied source/derivative conversion mapping. Keep video SHA, prediction SHA, original integer PTS/time base and any existing pixel hashes. Do not require ground scene calibration for a pose-only adapter.
3. Optional existing gait-review ZIP/JSON, paired fore/hind exports and explicit reviewed A/B->anatomical mapping. Preserve reviewer/exposure/adjudication status. No review means zero target-valid elements, not fabricated zero labels.
4. A small job specification referencing these existing files, canonical dog/provenance group and split, timing/rights status and optional pair mapping. It extends their metadata at conversion time; it does not edit existing manifests or replace the AP-10K pose-training manifest. Carry forward the DogReID training_approved gate and Dog02 exclusion policy. Unknown dog IDs/splits are allowed for inspection, forbidden for training-ready output.

Outputs into a new caller-selected, nonexisting directory:

- features.npz: float32 raw feature matrix [T,69], source frame indices, float64 source timestamps/delta times, keypoint observed mask [T,17], reference-valid mask [T], four-channel target values and independent target-valid masks [T,4], identity/visibility eligibility and segment/window metadata. Preserve original finite raw x/y/rawScore values at JSON precision in provenance/audit data; float32 model tensors are explicitly derived, never replacements for source JSON. Keep unknown reason codes outside binary targets.
- manifest.json: schema/feature version, exact channel/paw order, input hashes, dog/split/rights/exposure metadata, source/derivative linkage, normalization/threshold policy, window/padding policy and all eligibility counts. Store integer PTS plus rational time base losslessly; avoid object/pickle arrays.
- validation.json: structural/alignment findings, raw-score ranges including >1, missing/occluded/identity counts, independent valid-target counts by paw/state, timing-evaluation eligibility, excluded windows/reasons, trainingReady boolean and blockers.

The CLI should expose inspection/feature-only mode and --require-training-ready. Inspection may succeed on an unlabeled source and emit trainingReady=false. Training-ready mode must fail with a specific reason when labels, identities, splits or rights are unresolved. Unsupported timing cannot become evaluation-ready because the file contains numbers.

Existing functions to reuse:

- training.prepare_paw_annotations.{load_json,digest,checked,require,validate_predictions}: named AP-10K/schema/hash/count/time validation and unchanged-prediction contract.
- training.gait_event_review.{digest_bytes,validate}: existing review/provenance, support state, independence declaration and six-boundary consistency validation. A “valid” legacy ZIP is not proof of adjudication or no later exposure; the adapter must apply the explicit later exposure record and reject contradictory blind claims for evaluation readiness.
- src.petlens_gait.ground.validate_alignment: reuse for records meeting its S003 conversion contract. Its implementation expects conversion arrays and source metadata; call it only when those exist, otherwise use the same strict PTS/index checks through a generic join. Do not force every clip through a ground-extraction job or silently loosen its requirements.
- reports/dogreid-1553/build_review.py::validate_identity_splits: reuse canonical dog-level split logic, with a small explicit loader if needed because of the hyphenated directory. Extend the adapter's own checks to source/publication groups and derivatives; the existing function alone does not catch cross-pipeline leakage.
- Existing midpoint/neck-tail calculation in tmp/rtmpose-test/body-reference-comparison/run_body_reference_comparison.py::make_reference("B") and saved normalized-paws.csv semantics: promote only the small tested math into the stable adapter, without importing a temporary executable experiment or changing historical artifacts. Do not use method A's AP-10K “hip” landmarks as anatomical canine pelvic joints.

Pass/fail acceptance criteria:

1. Original Dog02 joins all 60 source frames to the same prediction/conversion indices and native times; Dalmatian joins all 177 rows without hiding its three missing pose frames. Nonmonotonic/duplicate timestamps, count/hash/schema/name mismatches, unknown joints and duplicate names fail loudly. A regular 0..59 time vector must not substitute for missing original PTS.
2. A 1.46 raw score survives unchanged in audit data and as an explicitly derived float32 feature; no [0,1] clipping or calibrated-confidence assertion. Synthetic NaN/inf, out-of-bounds and absent points preserve reason-coded missingness and produce finite masked model tensors. Duplicate frame/keypoint records are rejected rather than silently deduplicated.
3. Translating all valid keypoints leaves relative coordinates unchanged; uniform scaling leaves normalized coordinates unchanged. Zero/invalid neck-tail scale invalidates the frame; no fallback anatomical landmarks or ground-clearance fabrication.
4. Missing/low-score points, missing body reference and failed detections stay represented at their original frame/time. No coordinate/identity interpolation. Unknown/occluded/unreviewed states and unsupported A/B mapping have zero loss weight. Targets never come from candidate-events.csv, tracking output or the ground detector.
5. The saved Dog02 ZIP and its later exposure draft remain byte-identical; output reports zero independently adjudicated contact targets and trainingReady=false. The v2 Dalmatian 79 coordinate points alone yield no contact targets. No source is automatically finalized or promoted from exploratory to training.
6. Same canonical dog across splits, same source hash across splits, derivative overlap, unresolved publication grouping split apart, evaluation dogs in normalization/training, and unapproved DogReID rows all fail training-ready checks. Distinct windows from one dog cannot bypass the gate.
7. Window tests cover short padded sequences, final-window masking, no all-padding windows, native 12/30/60 FPS elapsed times, explicit discontinuity/identity breaks and no window spanning source/dog/split boundaries. Husky and uncertain-source 60 FPS material remain native-timing-evaluation-ineligible even with monotonic PTS.
8. Two explicit A/B pair exports can map to four paws only with supported fore/hind/anatomical identity metadata; absent/conflicting mapping fails supervised readiness. A labeled synthetic example proves valid BCE targets can be emitted, while no-label data proves no target fabrication.
9. Existing source/label hashes remain unchanged, existing output directories are never overwritten, no downloads/dependency/model imports occur, focused adapter tests and existing affected review/alignment tests pass. Run the established regression suite once after implementation if required by the repository workflow; today's historical 267 passes are not substitutes for those future checks.

Expected adapter blockers are missing original frame linkage for some legacy files, absent four-paw mappings, incomplete review/adjudication/exposure records and missing dog/rights assignment. They should produce an informative inspection report, not block writing/testing the adapter. A small all-masked feature export is an acceptable preparation result; it is not a successful training dataset.

7. BLOCKERS

Only material blockers for the next implementation/training decision:

1. No independently adjudicated contact/airborne training/evaluation sequence is currently available. Existing Dog02 reports cannot supply it, and neither pose visibility nor all-UNKNOWN rule output is a contact label.
2. Four-paw physical/anatomical continuity is not established by raw AP-10K channel names. Existing A/B references mainly concern hind paws; unresolved mappings must remain masked.
3. There is no verified dog-separated native-rate pilot cohort yet. Dataset UUIDs, cross-source identity grouping and derivatives must be resolved before split assignment. Existing 12 FPS footage cannot support fine timing claims; Husky and uncertain-source resampled clips are excluded.
4. Some legacy saved predictions lack a complete original-frame provenance envelope. Support them only with explicit verified metadata; the generic adapter can proceed on Dog02/Dalmatian now.
5. Commercial provenance is incomplete for some local stock/processed videos, the exact RTMPose artifact and ContactVision's human checkpoint/training inputs. This does not block a local saved-pose adapter or commercially permitted code adaptation. It blocks using uncleared media/weights in the commercial training/distribution path. Scratch canine contact weights and cleared capture avoid making the human checkpoint a dependency.

Decision: authorize the three-file adapter/validator task next, then complete the small reviewed pilot. No new backbone, image model, model search, annotation platform or training run is needed to take that next step.
