# S004 corrected observations — Version 2

Version 2 supersedes Version 1 for current working observations. All six V1
files are retained unchanged, with hashes recorded in the V2 event sidecar.
These are human-reported draft observations, with prior footage and annotation
exposure. They remain unapproved and non-independent.

| Physical paw | Corrected human-confirmed intervals | Change from V1 |
| --- | --- | --- |
| Hind A | Lift-off 16–19; touchdown 44–49 | These intervals were previously assigned to C |
| Hind B | Touchdown 7–8; lift-off 50–54 | Unchanged |
| Front C | Touchdown 5–10; lift-off 47–49 | These intervals were previously assigned to A |
| Front D | Lift-off 8–12; touchdown 35–40 | Unchanged |

The eight ranges are preserved exactly, including inclusive original endpoints
and their manifest PTS/time/hash records. Each paw has two nonoverlapping,
chronologically ordered events in opposite directions. Cross-paw overlaps are
allowed and do not establish conflicts. No additional events are invented.
The physical names remain A/B hind, C/D front; this is an explicit correction
of event associations, not an anatomical rename or automatic identity swap.

Front C's human description, **closer to the dog's head in the stationary
reference position**, is preserved. Its reference frame is unspecified.
The reviewer reports tracking all four paws throughout. That is sequence-level
human evidence, not automatic proof of per-frame visibility or support state.
No anatomical LF/RF/LH/RH mapping is assigned. The historical V1 Hind A recheck
stays in V1 and its lineage; it is not inferred to be a new V2 recheck of A or C.

All **240 support states remain UNKNOWN**, including frame 0. Visibility and
per-frame continuity remain unreviewed. UNKNOWN records are unverified
placeholders, not claims that all 240 frames were individually reviewed and
judged unassessable. Exact transition frames and definite boundary support
states remain null. No continuous stance/swing or complete stride is inferred.

Files, relative to `/workspaces/Petlens`:

- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v2.review.json`
- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v2.events.json`
- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v2.provenance.md`
- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v2.verification.json`
- `reports/canine-contact-batch-v1/drafts/s004-human-observations-v2.validation.json`

The provenance file preserves the corrected observations and reviewer notes
verbatim, then records version/exposure handling separately. The event sidecar
includes hashes and event-by-event links to V1. B/D's four unchanged intervals
can be retained without another occurrence-review pass, but they are the same
human's reports, not independent corroboration or definite frame targets.
No earlier workspace/browser audit was repeated. The old S003/Dog02 review
identified in V1 remains unrelated footage and is not imported.

The smallest next human task is **two Front C decisions, at original frames
4 and 11**, around its confirmed touchdown range 5–10. Record CONTACT/AIRBORNE,
visibility and continuity only if the original frames support them; otherwise
retain UNKNOWN and use adjacent original frames only as needed. These flanks
are candidates for evidence, not presumed labels. No exact transition frame or
full 240-label pass is required.

If those checks are usable, the remaining boundary flanks are:

| Paw | Lift-off flanks | Touchdown flanks |
| --- | --- | --- |
| Hind A | 15 and 20 | 43 and 50 |
| Hind B | 49 and 55 | 6 and 9 |
| Front C | 46 and 50 | 4 and 11 |
| Front D | 7 and 13 | 34 and 41 |

That is 16 paw-frame decisions across all eight transitions. Check a middle
gap for omitted transitions only when selecting it as a continuously labeled
training span or building a complete-cycle assertion: A **20–43**, B **9–49**,
C **11–46**, D **13–34**. Long gaps do not invalidate the reports. Unneeded
prefixes, tails and initial states can stay UNKNOWN and masked. When useful
for identity mapping, name the reference frame already used for Front C and
describe A versus B there; do not repeat the full tracking pass.

Use the existing reviewer:

```bash
cd /workspaces/Petlens
python -m training.gait_event_review \
  --dataset gait-s004 \
  --manifest reports/canine-contact-batch-v1/frame-manifest.json \
  --port 8767
```

Open `http://localhost:8767/?dataset=gait-s004` (or privately forward 8767 in
Codespaces). Start session `s004-requesting-user-written-v2`, declare prior
exposure, then import the V2 review JSON through the existing backup control.
Keep the V1 session untouched. Both session IDs represent the same human;
the version suffix prevents browser autosave from replacing V1. Download any
existing V2 work before importing a replacement. Use **frame number + Go** and
arrows; the checklist is read alongside the interface, not automatically loaded.
Save completed checks with the existing versioned partial ZIP export.

The source is the original 60-frame, 960×544 OGV with indices and PTS 0–59,
time base 1/12, and 83.33 ms movie-frame spacing. Image quality prevents exact
transition frames. Sensor-native capture timing remains unattested. The source
manifest, attribution, unresolved dog grouping and predictions are unchanged.

The existing review validator/export and contact-adapter loader accept V2.
All 240 training targets remain masked. Future binary supervision still needs
explicit visible frame states, verified anatomical mapping, the existing
independence/reconciliation and dog/split approvals. The adapter's current
supervised pair mapping expects A/B; front C/D needs an explicit,
provenance-preserving pair conversion or support before supervised import.
No mapping or adapter changes are made in this observation-update task.

**Next concrete step toward ContactVision training:** save the two Front C
flanking-frame checks as a new partial human review, preserving V2 event ranges
and prior exposure. That supplies potential frame-level evidence for the
existing approval pipeline. These interval-only drafts currently provide zero
supervised training targets.

Validation commands:

```bash
python -m pytest -q tests/test_s004_contact_draft.py tests/test_s004_contact_draft_v2.py tests/test_gait_event_review.py tests/test_contact_features.py
node tests/test_gait_event_review_ui.cjs
```

See the validation JSON for results and preservation hashes. No videos,
predictions, adapter/model code, earlier annotations, architecture.txt or unrelated
files were changed. No installs, downloads, inference, training, commits or pushes
were performed.
