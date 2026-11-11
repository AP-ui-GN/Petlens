# First authorized real-data contact experiment — 11 November 2026

**One real training run completed all five epochs. No second run was started.**

Data: one S004 source dog, one five-frame window (46–50), and exactly two real
approved Front C observations: CONTACT at 46 and AIRBORNE at 50. Frames 47–49
and all other unapproved labels remained masked. The reviewer had prior exposure;
anatomical side remains UNKNOWN. No synthetic labels entered this run.

| Epoch | Training BCE |
| --- | --- |
| 1 | 0.824490 |
| 2 | 0.699603 |
| 3 | 0.801229 |
| 4 | 0.706173 |
| 5 | 0.710068 |

Loss decreased overall but not monotonically. Deterministic forward-only checks
on the same training inputs, with dropout disabled, gave BCE **0.810656 before
training and 0.738537 after training**. These are training-set fit measurements,
not validation. Contact probabilities after training were **0.650953 at frame 46**
and **0.649276 at frame 50**. At threshold 0.5, it predicted CONTACT for both:
one of two positions correct. It has **not learned to distinguish both states**
in this run, and it is not a useful contact detector yet.

29 state tensors changed, including the temporal encoder/input projection and
physical readout. The frozen anatomical classifier stayed exactly unchanged.
All 29 optimized parameter tensors have nonzero AdamW first moments and five
recorded optimizer steps, confirming real gradient-based updates beyond weight
decay. Direct per-step gradient norms were not logged; this evidence comes from
the saved optimizer state and initial/final weight comparison.

The initialization reference used the exact CLI seed/configuration and model
constructor before the run. Its consistency was checked against the unchanged
random frozen classifier and reproduced baseline loss. Checkpoint reload
matched every saved tensor and reproduced final forward outputs exactly.

Checkpoint: `outputs/contact-s004-physical-c-v1/last.pt`.
Training configuration, metrics, authorizations, attribution, source evidence,
provenance and verification files are saved alongside it. Detailed results are
in `training-fit-verification.json` and `gradient-and-parameter-verification.json`.

## Authorization and rights

The owner explicitly directed execution after reporting **“I approve.”** following
the six-item checklist. `owner-authorization.CONVERSATION-v1.json` records the
current instruction, date, exact reported approval and scope. The approver is
identified only as the requesting project owner in this conversation. Legal
name and handwritten signature are null; none was invented. The unsigned
template and unapproved job version remain preserved.

Rights were checked separately from that approval. The
[publisher's article](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0059875)
identifies Movie S4 and attributed reuse. The
[Commons file page](https://commons.wikimedia.org/wiki/File:Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s004.ogv)
shows CC BY 2.5 in its license box and CC BY 3.0 in metadata; the original local
file's saved probe also records 3.0. Both
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) and
[CC BY 2.5](https://creativecommons.org/licenses/by/2.5/) permit reproduction
and adaptation, including commercial uses, with attribution. The assessment
that this bounded local feature-derived fitting falls within those grants is
an inference, not an assertion that the authors gave AI-specific permission.
Both notices, the discrepancy, source links, author credit, modification notice
and no-endorsement statement were retained in `ATTRIBUTION-v1.txt`.

Local source, working video, predictions, labels and authorization hashes were
verified. S003/S004 retain the conservative shared grouping; there is no claim
that they depict different dogs or that the clinical subject's individual
identity has been established. Source-movie PTS are preserved; native camera
capture timing remains unattested.

## Limits and next action

This demonstrates that two genuine approved canine observations reach a real
loss, update the network and produce a reloadable checkpoint. It does not
establish reliable contact recognition, anatomical mapping, event timing,
generalization, clinical validity or other-dog performance. The source-bound
readout can memorize sequence phase or pose context and cannot identify an
arbitrary physical paw in a new video.

**One next action:** obtain a rights-cleared side-on clip of one clearly different
dog and independently label a contiguous contact/airborne span, with explicit
paw identity. This adds the first distinct-dog evidence toward a useful
multi-dog model rather than repeatedly optimizing these two observations.

All existing annotations, videos, predictions, adapter, model and training code
remained unchanged. Only the requested job reference/approval fields changed;
its previous version was saved. No installs, model downloads, commits or pushes.
