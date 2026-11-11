# S004 human contact observations — draft, 11 November 2026

All four physical paws and eight human-confirmed transition intervals are
preserved. These are human reports, not automatically verified ground truth.
Hind A's recheck confirmation is retained. No anatomical side was assigned.
The reviewer has previously seen the footage; this is a non-independent review.

Files in this directory:

- `s004-human-observations-v1.provenance.md`: original supplied observations,
  verbatim, including identity method, Hind A recheck, timing and exposure history.
- `s004-human-observations-v1.review.json`: existing reviewer schema, importable
  under session ID `s004-requesting-user-written-v1`.
- `s004-human-observations-v1.events.json`: typed interval sidecar with source,
  frame-manifest and draft hashes; verbatim provenance; earlier-record comparison;
  missing evidence and exposure declarations. The core schema cannot express
  these ranges without pretending their endpoints are definite frame states.
- `s004-human-observations-v1.verification.json`: targeted checks for existing
  reviewer navigation, with priorities and exact original frame ranges.
- `s004-human-observations-v1.validation.json`: validation and preservation results.

## Confirmed reports and UNKNOWN states

| Physical paw | Human-confirmed event intervals, inclusive | Main unverified gap |
| --- | --- | --- |
| Hind A | Touchdown 5–10; lift-off 47–49; reviewer rechecked both | 11–46 |
| Hind B | Touchdown 7–8; lift-off 50–54 | 9–49 |
| Front C | Lift-off 16–19; touchdown 44–49 | 20–43 |
| Front D | Lift-off 8–12; touchdown 35–40 | 13–34 |

An interval locates a transition. It does not assert CONTACT or AIRBORNE at
every frame, or establish a last-definite/first-definite support bracket.
Exact transition frames and all definite support-state boundaries are null.
All **240 paw-frame support states remain UNKNOWN**, including frame 0.
Visibility and per-frame continuity remain unreviewed. UNKNOWN here explicitly
means unverified from the written observations; it does not claim someone
visually reviewed all those frames and judged them unassessable. No stride
assertions or intermediate cycles were invented; zero complete strides exist.

The reported opposite events are ordered consistently for each paw. No internal
conflict was found. The long hind-paw gaps do not invalidate the reports, but
neither do they establish uninterrupted stance. The front-paw gaps likewise do
not establish uninterrupted swing. Check each named gap for omitted transitions
and visible frame states; retain UNKNOWN where evidence is poor.

## Earlier sessions and preservation

The November 3 setup at
`tmp/rtmpose-test/paw-tracking-experiment/manual-annotation/s004/manifest.json`
is bound to the same original S004 source hash. Its README and
`tmp/wikimedia-s004-preparation/REPORT.md` describe blank physical hind A/B
annotation and original-frame evidence, not saved human contact labels.
These assets can supply source provenance, but no S004 human-label JSON/ZIP was
found in the workspace, including ignored temporary files and relevant archives.
No saved S004 exposure declaration was found there.

The earlier saved contact export
`reports/gait-event-review-v1/reviews/review-d684d28c840a475ba7833f1c045d2504.zip`
belongs to **S003/Dog02**, reviewer `reviewer-1`, with a different video hash.
It stores `no_prior_exposure`; its separate written-observation proposal at
`reports/gait-event-review-v1/drafts/dog02-reviewer-1-written-observations-v1.proposal.json`
records `prior_exposure` as a correction awaiting confirmation. Both remain
unchanged. Their event/frame labels cannot be reused as S004 evidence.
Other inspected review ZIPs contain no S004 records. The sidecar records exact
paths and hashes. No same-source earlier human labels were available for a
label-by-label comparison; nothing was merged or overwritten.

Live browser localStorage was **not accessible**. An unexported earlier session
may still exist in the reviewer's browser. Its absence from disk does not erase
that history. The new source reviewer is explicitly `prior_exposure`, with prior
footage exposure true. Model-output/previous-annotation exposure was not specified
by this task. The existing schema's required `blind`, `modelExposed=false` and
`previousLabelsExposed=false` fields describe this draft's viewer/input workflow;
they do not establish lifetime non-exposure or supersede `prior_exposure`.

## Targeted verification using the existing reviewer

Run from `/workspaces/Petlens`:

```bash
python -m training.gait_event_review \
  --dataset gait-s004 \
  --manifest reports/canine-contact-batch-v1/frame-manifest.json \
  --port 8767
```

Open `http://localhost:8767/?dataset=gait-s004`, or forward port 8767 privately
in Codespaces. Startup verifies the source video and all original frame hashes.
The original 60-frame manifest stays unchanged. There is no automatic focused
queue/import of the checklist; use the existing frame number + **Go**, arrows,
Previous/Next and slow playback. No model predictions supply support states.

For the source reviewer, enter `s004-requesting-user-written-v1`, start that
dedicated session, declare **prior exposure**, and import the matching
`s004-human-observations-v1.review.json` with the existing backup control.
If that session already contains work, download its backup and retain it before
working separately on this draft; do not overwrite an existing browser review.
Other humans start their own blank sessions and keep their own identity/exposure
declarations. The sidecar supplies context for this exposed review, and is not
automatically loaded into an independent review.

Review only the requested paw in each main gap above, recording definite visible
frame states and checking for additional transitions. For boundary evidence,
check these flanking frame pairs first; use the span between them for context
only if needed. These are requested checks, **not presumed support states**:

| Paw | Touchdown flanks | Lift-off flanks |
| --- | --- | --- |
| Hind A | 4 and 11 (context 4–11) | 46 and 50 (context 46–50) |
| Hind B | 6 and 9 (context 6–9) | 49 and 55 (context 49–55) |
| Front C | 43 and 50 (context 43–50) | 15 and 20 (context 15–20) |
| Front D | 34 and 41 (context 34–41) | 7 and 13 (context 7–13) |

Hind A's event occurrence/ranges are already rechecked. Its requested checks
address missing frame states and intermediate transitions; they do not demand
another occurrence confirmation or a narrower interval.

At one visible reference frame in **0–4**, add the existing physical assignment:
which hind paw was called A versus B, and which front paw C versus D, using the
reviewer's headward/rearward distinction. If none of 0–4 works, name another
visible reference frame. The task reports physical continuity throughout, with
no reported breaks, but does not say which letter occupied which reference
position. Preserve the reviewer's assignment; leave anatomical sides unresolved.

Initial states at **0 for all four paws** remain missing. Unverified prefix/tail
portions are A **0–4 / 50–59**, B **0–6 / 55–59**, C **0–15 / 50–59**,
D **0–7 / 41–59**. If these portions are needed later, check 0 and 59 first and
expand only as useful; otherwise keep them masked. They need not be relabeled
to use a shorter verified interior span.

Record visibility, physical identity continuity and CONTACT/AIRBORNE only where
the original frames support them. Keep uncertainty when the video cannot resolve
it. Save any revised evidence as a new version. Use **Validate, save & download
versioned ZIP** for new review exports; partial/UNKNOWN exports are allowed and
remain unapproved. No request to redo all 240 paw-frame decisions is made.

## Timing and training compatibility

Frame indices remain 0–59, integer original PTS 0–59, time base 1/12, and timestamps
0–59/12 seconds. The original OGV is 960×544 at 12 FPS, one frame every 83.33 ms.
Poor visibility adds the supplied multi-frame uncertainty. Do not estimate a
midpoint, invent subframe precision, or treat source-movie FPS as independently
attested sensor timing. Source rights, attribution and the unresolved dog identity
group remain in the unchanged manifest.

The draft passes the existing review validator and export round trip. The
existing contact adapter can inspect the four-paw review JSON. Its binary
training targets cannot use these intervals directly: all 240 targets stay
masked. The sidecar preserves event evidence without changing the 69-channel
adapter, review schema, model or rule baseline.

There is a concrete existing adapter limitation: its supervised fore/hind
mapping contract expects physical **A/B per pair**. S004 uses **C/D** for the
front paws. Later supervised conversion must explicitly preserve the original
C/D IDs in provenance through a named pair projection, or support those IDs in
the adapter. No projection, anatomical mapping or silent rename is made here.
This is not ready for supervised front-paw import today.

These labels are **not sufficient for a supervised training experiment**: there
are eight interval observations but zero definite frame targets. Missing evidence
is visible frame states/continuity on usable spans, any intermediate events,
reference physical-paw anchors, separately verified anatomical mapping, and the
existing independent-review/reconciliation gate. Dog identity/split approval
remains open. The existing multi-dog pilot gate (three adjudicated complete
strides across two identified dogs) is not satisfied by this single draft.
Native capture timing remains unverified; fine-timing evaluation is unsupported.

**One next action:** use the existing reviewer to check **Hind A 11–46** for
visible frame states and any omitted transitions, then save a new versioned
partial review. Keep its rechecked event ranges and prior-exposure declaration.
This creates actual potential frame supervision without repeating model research
or rebuilding tools.

Validation commands:

```bash
python -m pytest -q tests/test_s004_contact_draft.py tests/test_gait_event_review.py tests/test_contact_features.py
node tests/test_gait_event_review_ui.cjs
```

Validation includes all 60 source-frame hashes, original PTS/time alignment,
uncertain event boundaries, exact physical IDs, exposure, existing export/load
compatibility, zero training masks and targeted checks. See the validation JSON
for execution results and the preservation snapshot. No training, installs,
downloads, video/prediction changes, commits or pushes were performed.
