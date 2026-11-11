# First real S004 training experiment: blocked review packet

**Can we train now? NO.** No run was attempted and no weights or training
metrics were produced. This directory contains genuine saved-pose features and
human observations for review, not an approved training dataset or runnable job.

The saved features convert successfully to **60 × 69**, with 60 eligible body
references and one padded feature-only window. All 240 loss masks are false.
That window does not certify paw continuity or supply supervision. Candidate
frame pose observations are eligible under either possible anatomical channel
within the correct fore/hind pair; this does not determine which channel is the
actual physical paw.

## Actual observations

| Physical paw | Conflict-free CONTACT assertions | Conflict-free AIRBORNE assertions |
| --- | --- | --- |
| Hind A | 15, 50 | 20 |
| Hind B | 9, 49 | 55 |
| Front C | 11, 46 | 50 |
| Front D | 41 | none |

These are **10 candidate assertions: 7 CONTACT and 3 AIRBORNE, zero approved
supervised observations**. A43 remains disputed and excluded. D13 remains
provisional; C4, D7, D34 and B6 remain UNKNOWN. The other 224 slots remain
unreviewed. All 16 original statements, confidence, frame references and
exclusions are retained in `observations-for-review.json`; uncertain event
intervals remain referenced by hash and never generate frame labels.

## Smallest useful human task

Check **Front C, original frames 46–50**, a five-frame span lasting 0.333 seconds
between endpoints. The existing human reports C46 CONTACT and C50 AIRBORNE.
Confirm or correct those endpoints and record visible paw identity/continuity
on all five frames; interior contact states may remain UNKNOWN. If visibility
or continuity cannot be established, keep the affected frames masked. This is
a proposed minimal optimization check, not enough evidence to learn reliable
temporal behavior. A43 need not be resolved for this selected span.

Under the **current** `prepare_contact_sequences._labels` policy, obtaining
approved labels requires **two genuinely independent, previously unexposed
human reviews**, plus a separately recorded human reconciliation. V1–V3 are
one exposed reviewer and count as neither independent review. Changing a
reviewer ID or approving the draft alone cannot satisfy that rule. Both new
reviewers must use the original footage without reading this packet, V3 labels,
or predictions; give them only the neutral frame range and paw-description
task. A resolver must reconcile their own physical paw names before mapping.
Partial review exports are supported: no 240-label pass is required.

Use the existing reviewer:

```bash
python -m training.gait_event_review \
  --dataset gait-s004 \
  --manifest reports/canine-contact-batch-v1/frame-manifest.json \
  --port 8767
```

Each independent person starts their own blank session, describes the tracked
limbs, reviews the selected span, and exports a versioned partial ZIP. Do not
import V3 into a session intended to be independent. The original exposed
reviewer can still supply separate mapping or reconciliation evidence while
retaining their exposure declaration.

`human-review-request.json` is an unsigned form, not approval. All four physical
paws have explicit roles; anatomical assignments remain null. Hind A/B must
map to LH/RH and Front C/D to LF/RF only with human evidence. For the smallest
front-only experiment, establish the forepaw mapping and leave hind outputs
unsupervised; do not invent hind anatomy. Also record a conservative verified
source/dog grouping, keeping S003/S004 and related material out of validation
and test, and explicit training authorization with rights evidence/attribution.

## Single-dog engineering versus multi-dog evaluation

A train-only engineering check needs real approved binary observations, verified
mapping/continuity for supervised paws, source hashes/timing, rights, and explicit
training approval. One dog, one contiguous window, one supervised paw with both
states, fixed bounded steps and a final checkpoint can demonstrate real-data
optimization. A validation dog, all-paw class coverage and a measured native
camera rate are not intrinsic requirements for that limited check. Available
OGV timestamps remain real source-movie timing; no sensor timing is invented.

However, **the existing implementation currently enforces those broader gates**:

- `prepare_contact_sequences._labels`: two independent reviews, reconciliation,
  explicit A/B anatomical pair mapping. It currently reads A/B for forepaws as
  well as hind paws; S004 C/D requires explicit provenance-preserving import
  support, not relabeling the original files.
- `prepare_contact_sequences._prepare_one`: dog identity, approval, provenance,
  cleared rights evidence and attested native timing.
- `prepare_contact_sequences.build`: both states for all four training paws.
- `train_contact.load_prepared` and `train`: supervised validation dogs and
  validation-loss checkpoint selection.

An explicit exploratory mode is therefore needed in these existing utilities
after the scoped timing/partial-paw/train-only policy is approved. It should
keep independent label review, source/identity/rights checks and masks intact,
have no validation metrics or best-validation checkpoint, and preserve the
current stricter defaults. No policy has been waived or silently changed here.
The unsigned request records those exact scope decisions. A config file alone
cannot make the present trainer accept this run.

For meaningful multi-dog evaluation, obtain additional independently identified
dogs in disjoint training, validation and locked test sets, all-paw/state
coverage, and timing suitable for the claims being measured. S004 training fit
cannot provide generalization accuracy or clinically meaningful gait results.
The immediate next multi-dog step is one clearly different, rights-cleared dog
with independently reviewed paw labels, while retaining all related S004
sources in the training group.

## Rights and preservation

The local rights record documents attributed reuse with embedded CC BY 3.0 and
Commons CC BY 2.5 notices; both notices and the discrepancy are retained in
`attribution.json`. This packet does not replace that record with a self-issued
`cleared` or `trainingApproved` flag. The named human approver must bind their
training authorization to that evidence and retained attribution. Current
status remains `attribution_required`, not the preparer's required `cleared`.

`preservation.json` records unchanged hashes for 34 existing source, annotation,
model, adapter, trainer and unrelated modified files. V1–V3, video, predictions,
RTMPose and the rule baseline were not changed. No installs, downloads, commits
or pushes occurred.

**Next human action:** arrange the two independent partial reviews of frames
46–50 and complete the mapping/rights/train-only approval request. Do not repeat
all 60 frames or repair A43 merely to start this selected experiment.
