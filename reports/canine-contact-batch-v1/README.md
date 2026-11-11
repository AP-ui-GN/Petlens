# First canine contact review batch — 11 November 2026

One clip is ready for cautious human labeling: **Shin et al. Movie S4 (S004)**,
60 consecutive frames, 0–59, at 960×544 and 12 FPS. This is the brown affected
dog walking side-on in a laboratory. Visible paw/surface evidence can be reviewed;
far-limb overlap, dark flooring and blur must remain UNKNOWN where unclear.
This is not a healthy reference dog or a fine-timing benchmark.

Original video:
`tests/Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s004.ogv`

We did not find two eligible clips. Dalmatian has the best higher-resolution
side view but lacks a verified commercial reuse/source record. DogReID #115
and #198 retain their review-only status: elevated view, ambiguous far-paw
contact, #198 walk/trot uncertainty, and unattested original capture timing.
Their CC0 rights record does not fix these visibility/timing issues. The other
15 local DogReID clips have documented rejection reasons in
`reports/dogreid-1553/screened-videos.csv`. Dog02 remains exploratory-only.
The Husky screen recording is excluded from native gait-event timing.

## Open the existing reviewer in Codespaces

Run in a Codespaces terminal:

```bash
cd /workspaces/Petlens
python -m training.gait_event_review \
  --dataset gait-s004 \
  --manifest reports/canine-contact-batch-v1/frame-manifest.json \
  --port 8767
```

Wait for `Provenance verified for gait-s004`. In Codespaces **Ports**, forward
port **8767** if it is not already listed, keep it private, and click **Open in
Browser**. Append `/?dataset=gait-s004` to the forwarded address if necessary.
Local URL: `http://localhost:8767/?dataset=gait-s004`.
The server verifies the original video and all frame hashes at startup and
fails if they differ. No installs, model downloads or inference are needed.
Stop the server with Ctrl+C when finished.

## What you label

1. Enter your own reviewer ID and click **Start / resume only my review**.
   Declare prior exposure honestly. If you have seen predictions or prior contact
   labels for this footage, select prior exposure; your work is retained but
   cannot count as the independent reference.
2. Watch the whole clip first using slow playback. Follow four physical limbs:
   **A and B are the two hind paws; C and D are the two front paws.** Describe
   each in the description boxes using visible anatomy or identifying features.
   You choose which hind limb is A and which front limb is C; keep that choice
   stable through the entire sequence. These letters are not anatomical left/right
   or screen order. Anatomical mapping must later be checked separately.
3. For every frame and every paw, record visibility, identity continuity and
   **CONTACT** (visibly touches the walking surface), **AIRBORNE** (visibly off
   the surface), or **UNKNOWN** (cannot determine). UNKNOWN is different from
   Not reviewed. Record occlusion/missing evidence in visibility and notes.
   If identity is uncertain or continuity breaks, use UNKNOWN; do not guess
   which limb emerged from overlap. Definite labels require a described limb,
   visible paw and reliable continuity. Do not infer contact from a shadow or
   a predicted point. The server never serves predictions or previous labels.
4. Use arrow keys, Previous/Next or frame number + Go to step. Select each of
   the four paws on every frame. Uncheck **Fit frame to screen** to enlarge.
   Frame numbers are zero-based, with timestamps from the original OGV.
5. Use **Download my draft backup** regularly. When finished, click **Check
   review**, then **Validate, save & download versioned ZIP**. Stride assertion
   controls are optional for this first contact-labeling batch; leave them blank
   unless you can independently support the event brackets.

Workload: **60 frames × 4 paws = 240 decisions per reviewer**. There are
currently zero human contact decisions in this batch. Blank records are
created on starting a reviewer session; no fake ground truth has been saved.

## Independent storage and disagreement review

Browser autosave is separate for each manifest, dataset and reviewer ID.
A second person uses a different ID and preferably a separate browser profile.
They must judge the original footage independently and not inspect the first
person's labels. Changing IDs alone does not make a person independent.
Importing another reviewer's backup is blocked.

Exports are new, uniquely named ZIPs in:
`reports/canine-contact-batch-v1/reviews/review-<unique-id>.zip`

Each ZIP contains the human `review.json`, source-bound `frame-manifest.json`,
`validation.json`, and a manifest with reviewer, export time, source hash,
exporter hash and output hashes. The frame manifest retains integer original
PTS, time base, timestamps, pixel and PNG hashes. Observations retain all four
physical paw IDs, visibility, continuity, uncertainty and notes. No model
output is copied into labels. Partial reviews can be exported without forcing
labels or events. Partial/UNKNOWN records remain unsupervised.

After both independent exports are complete, a resolver must inspect their
limb descriptions and confirm which physical paws correspond. Then run, using
the actual two ZIP filenames and the confirmed correspondence:

```bash
python -m training.gait_event_review \
  --compare reports/canine-contact-batch-v1/reviews/review-FIRST.zip \
            reports/canine-contact-batch-v1/reviews/review-SECOND.zip \
  --paw-map A:A B:B C:C D:D \
  --comparison-output reports/canine-contact-batch-v1/disagreements-v1.json
```

The paw map shown is an example, not a pre-approved mapping. If the second
reviewer called the opposite hind paw A, use `A:B B:A`. Comparison rejects
different source provenance, identical reviewer IDs and declared prior exposure.
It flags contact, visibility and continuity differences and incomplete records,
preserves both reviews and produces no consensus labels. Human resolution must
be stored separately with resolver identity and evidence; neither matching labels
nor this comparison automatically approves training.

## Timing, identity, rights and remaining blockers

All 60 original integer PTS run from 0 to 59 with time base 1/12:
timestamps 0 to 4.916666667 seconds, interval 83.333 ms. These are reliable
timestamps for this available OGV movie. Original camera sampling is not
independently attested; 12 FPS is not evidence of a native 12 FPS camera.
Do not interpolate event times or use playback speed as source timing.

The saved RTMPose-m AP-10K predictions contain all 60 indices/timestamps at
`tmp/rtmpose-test/multi-video-evaluation/runs/wikimedia-s004-cfr-20261103/predictions.json`.
The existing input `tmp/wikimedia-s004-preparation/s004-lossless-cfr.mp4`
matches all 60 source decoded frames exactly in the current environment.
Neither file was regenerated. Predictions remain hidden from reviewers.

The source's [publication](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0059875)
permits attributed reuse. Original embedded metadata states
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/); the
[Commons file description](https://commons.wikimedia.org/wiki/File:Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s004.ogv)
states [CC BY 2.5](https://creativecommons.org/licenses/by/2.5/).
Both permit commercial reuse with attribution. Retain this version discrepancy,
author credit, source/license links and change notices with any reused data.
Credit: Shin J-H, Greer B, Hakim CH, Zhou Z, Chung Y-c, Duan Y, He Z, Duan D
(2013), Movie S4, *Quantitative Phenotyping of Duchenne Muscular Dystrophy Dogs
by Comprehensive Gait Analysis and Overnight Activity Monitoring*, PLOS ONE,
DOI 10.1371/journal.pone.0059875. Original OGV unchanged; PNG extraction and
human annotation are derivatives; no author endorsement is implied.

Training remains blocked by missing independent contact labels, disagreement
resolution, verified anatomical LF/RF/LH/RH mapping and dog identity/split
approval. S003 and S004 remain in conservative identity group
`shin-2013-s003-s004-unresolved`; S004 is not certified as another dog distinct
from Dog02. Its clinical source description is retained. Native capture timing
remains unverified. Adapter-ready contact-label conversion is deferred until
real reviewed labels and physical/anatomical mapping exist; existing feature
inspection artifacts are unchanged. This batch has `trainingApproved=false`.

Smallest addition for a two-dog start: **one** clearly identified different dog's
side-on walking clip, ideally 5–10 seconds, all four paws visible on a hard,
contrasting surface, minimal overlap, reliable original capture timestamps and
explicit permission for labeling and commercial model development. Resolving
Dalmatian source rights may avoid acquiring another clip if its timing and
physical identity checks also pass. No eight-dog pilot is required to label this
batch. No training, downloads, installs, inference, commits or pushes were run.

Validation commands (HTTP tests need local socket permission):

```bash
python -m pytest -q tests/test_gait_event_review.py
node tests/test_gait_event_review_ui.cjs
```
