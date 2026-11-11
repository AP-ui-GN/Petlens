# S004 Version 3 — sparse human frame evidence

V3 supersedes V2 as the working draft and adds exactly **16** human frame
observations. All V1/V2 files and all eight V2 event records are unchanged.
This is the same previously exposed reviewer; no observations are described as
independent ground truth or approved training targets.

| Physical paw | Definite human CONTACT assertions | Definite human AIRBORNE assertions | Provisional | Reviewed UNKNOWN |
| --- | --- | --- | --- | --- |
| Hind A | 15 (80%); 43 ("pretty confident"); 50 (100%) | 20 (100%) | — | — |
| Hind B | 9 ("very confident"); 49 (no numeric confidence) | 55 (100%) | — | 6 |
| Front C | 11 (high confidence, identity confirmed); 46 (approximately 80%) | 50 (100%) | — | 4 |
| Front D | 41 (95%) | — | 13 AIRBORNE, moderate confidence | 7, 34 |

There are **11 non-provisional human state assertions** (8 CONTACT, 3 AIRBORNE),
**1 provisional AIRBORNE assertion**, **4 reviewed UNKNOWNs**, and **224 unverified
paw-frame slots**. A43 is included in the 11 assertions and separately flagged
as contested. "Definite" here means a human assertion of a state; it does not
mean independently confirmed, conflict-free, approved or above a new numeric
threshold. The 80% assertions retain the supplied confidence; qualitative
confidence never receives an invented percentage. Confidence is not a loss weight.

UNKNOWN reasons are retained verbatim: C4 poor quality prevents assessment;
D7 apparent partial touch is unreliable; D34 extremely close with possible
contact; B6 extremely close. They remain UNKNOWN even where contact sounds
plausible. No request is made to repeatedly inspect these same unclear frames.

The core review uses `uncertain` for D13, preserving the actual reported
AIRBORNE state, "moderate confidence" and "Provisional" in notes and the frame
sidecar. It cannot silently become a definite binary target. Remaining slots
are `unreviewed`, distinguishing them from the four reviewed UNKNOWNs. No gaps,
initial states, complete strides or anatomical sides are inferred.

For definite records, core visibility encodes the human's direct state report;
core continuity carries the V2 human declaration of tracking all physical paws
throughout. Only C11 received additional explicit frame-specific identity
confirmation. This provenance is recorded per observation and does not establish
visibility/continuity on unreviewed frames. The required legacy blind/session
flags do not override the explicit `prior_exposure` history in core and sidecars.

## Preserved discrepancy

Hind A **CONTACT at 43**, described as "pretty confident," precedes the
original **touchdown range 44–49**. Both remain intact and flagged unresolved.
It is inconsistent with interpreting 44–49 as the first return to contact after
lift-off 16–19. Both could coexist if an additional lift-off/touchdown happened,
but no such events are supplied or invented. No event is moved to 43, no exact
touchdown time is inferred, and CONTACT through 43–50 is not filled.

The conflict record blocks the contested frame/event from approval pending a
separate human resolution. A43 remains visible as the actual human report,
rather than being silently erased or changed to match the old interval.

## Files

All paths are relative to `/workspaces/Petlens`:

- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v3.review.json`
  — existing review schema, all 240 slots, only 16 explicitly observed.
- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v3.frames.json`
  — exactly 16 source-bound records with raw statements, status, confidence,
  identity evidence, provenance, version hashes and approval exclusions.
- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v3.events.json`
  — all eight original V2 event objects unchanged; discrete new frame evidence
  remains separate from uncertain transition intervals.
- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v3.provenance.md`
  — original event/frame statements and discrepancy wording, followed by explicit
  encoding/exposure notes.
- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v3.conflicts.json`
  — one unresolved Hind A discrepancy, linking both sources and a targeted check.
- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v3.verification.json`
  — the 16 completed checks and only the remaining targeted follow-up.
- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v3.validation.json`
  — source alignment, evidence counts, training readiness, tests and preservation.

## Next action and training readiness

**Reconcile only Hind A original frames 43–49**, using the existing reviewer.
Record whether A43 or the original touchdown range needs a documented correction,
or whether an additional transition is actually visible. Keep uncertainty if
the footage cannot settle it. Preserve all existing evidence and save any
correction/resolution separately. The other 15 supplied frame observations do
not need repetition for this discrepancy. D13 can remain provisional and excluded.

```bash
cd /workspaces/Petlens
python -m training.gait_event_review \
  --dataset gait-s004 \
  --manifest reports/canine-contact-batch-v1/frame-manifest.json \
  --port 8767
```

Open `http://localhost:8767/?dataset=gait-s004`. Start the separate
`s004-requesting-user-written-v3` session, retain prior exposure, import the V3
review JSON via the backup control, then use **frame number + Go** and arrows.
Keep V1/V2 browser sessions untouched. Back up any existing V3 work before
importing a replacement. All versioned IDs are the same human, not independent
reviewers. Save new work with the existing versioned partial ZIP export. Keep
confidence, event and conflict sidecars alongside that export: the core
reviewer does not automatically load or enforce sidecar conflict resolutions.

Three lift-off observations now have definite human CONTACT/AIRBORNE flanks:
A15/A20, B49/B55 and C46/C50. These are discrete states, not fully checked spans.
Touchdown-before states remain missing at C4, B6 and D34; D's lift-off flanks
remain UNKNOWN/provisional. Do not redo the 16 checks merely to fill those gaps.
Only acquire additional evidence when required for a selected usable span.

No training is ready yet: the existing adapter correctly keeps all 240 targets
masked because the review is non-independent, unadjudicated and anatomically
unmapped. The A43 discrepancy and D13 provisional state have explicit exclusions.
Current C/D front-paw identifiers also need the already documented explicit
provenance-preserving conversion/support before supervised pair import. Dog/split
approval and the existing pilot gates remain open; no entire stride is verified.

V3 is measurable progress from interval-only evidence: it contains 11 explicit
non-provisional state assertions, with their confidence and limits preserved.
Resolving the one named discrepancy is the next highest-value step toward a
coherent label set for the existing ContactVision training path. No architecture,
model selection, annotation app or feature-adapter work is introduced.

Validation commands:

```bash
python -m pytest -q tests/test_s004_contact_draft.py tests/test_s004_contact_draft_v2.py tests/test_s004_contact_draft_v3.py tests/test_gait_event_review.py tests/test_contact_features.py
node tests/test_gait_event_review_ui.cjs
```

The source remains 60 original frames, 960×544, PTS 0–59 and time base 1/12.
Exact event frames remain uncertain; no subframe timing or native sensor-rate
claim is made. Source videos, predictions, existing code, all earlier labels,
architecture.txt and unrelated files remain unchanged. No installs, downloads,
inference, training, commits or pushes were performed.
