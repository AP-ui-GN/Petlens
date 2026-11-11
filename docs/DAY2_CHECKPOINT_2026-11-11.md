# PetLens Day 2 checkpoint — 11 November 2026

Neural model, 69-channel adapter, masked trainer and identity-neutral exploratory
path are implemented. Synthetic execution/update/checkpoint tests pass. One
authorized real S004 run finished five epochs using two observations, changing
29 parameter tensors; its checkpoint reloads exactly. It predicted CONTACT for
both observations, so real-world contact/gait accuracy is **not validated**.
S004 V1–V3, exposure, uncertainty and conflict records remain preserved.

Synthetic-data verdict: **CONDITIONAL**. MuJoCo + dm_control is Apache-2.0 and
offers mechanics-derived contacts. The primitive quadruped lacks honest canine
AP-10K landmarks and a supplied walking controller. AI video supplies no reliable
contact truth; inspected canine datasets are research-only. See
[the bounded feasibility decision](SYNTHETIC_GAIT_FEASIBILITY_2026-11-11.md).
No simulator was installed and no additional model was trained.

## Validation

- Full Python suite: **634 passed, 68 subtests passed** using the existing
  `.venv-canine-v2`; localhost tests ran with sandbox permission.
- Three reviewer JavaScript checks passed, including four-paw controls,
  blind-review navigation and legacy paw-review behavior.
- Dependency-free API analyze-gate, explanation and hosting checks passed.
  Full API tests/typecheck were not completed: the pnpm wrapper attempted a
  registry preflight, which was stopped without installation; a direct test
  confirmed missing `zod`, and Express is absent locally. This environment
  limitation is not reported as a passing app suite. No app source changed.
- Credential-pattern and staged-content review excludes secrets, credential
  directories, private media, model weights, archives and unrelated artifacts.
  Reviewer IDs are generic role/session identifiers; legal names/signatures are
  absent. Conversational owner authorization records are project provenance,
  not authentication credentials. Selected NPZ arrays load with pickle disabled.

## What Git does not back up

The real checkpoint is **995,736 bytes**, but repository policy ignores
`outputs/`; it was not force-added. It remains at:

`outputs/contact-s004-physical-c-v1/last.pt`

SHA256: `930c67e805fa2fe65906731e2f476d0a3199a3a7d54beaf7b79212662fbc6789`

**A Git push does not back up these model weights.** Metrics, configuration,
source/rights/authorization evidence, parameter-update verification and results
are checkpointed as small records under
`reports/canine-contact-batch-v1/identity-neutral-exploratory/`.

Future reproduction command, after restoring the exact hashed input files and
matching the recorded environment, with a new output directory:

```bash
.venv-canine-v2/bin/python -m training.train_contact \
  --job reports/canine-contact-batch-v1/identity-neutral-exploratory/training-job.json \
  --config training/contact_identity_neutral_config.json \
  --output-dir outputs/contact-s004-physical-c-reproduction
```

This command was **not run again**. A different environment or serialization
version need not reproduce the exact checkpoint byte hash.

The **152 MiB Dalmatian lossless derivative** also remains local:

`tmp/rtmpose-test/multi-video-evaluation/inputs/dalmatian-lossless-cfr.mp4`

SHA256: `13efcd61041c8795852ad377ca4a969d117c907fcb8d4a9298c61303bb7881d8`

Its original local input is `tests/13792872-hd_1080_1920_30fps (1).mp4`.
The exact historical encoding recipe was not verified; keep this file rather
than assuming bit-for-bit regeneration. Rights clearance remains incomplete.
Also local: ignored S004 working video/prediction metadata, downloaded rejection
videos and inspection images, raw caches/pose weights, random initial-weight
snapshot, the pre-existing 51 MB pilot archive and Husky screen-recording ZIP.
None was deleted or uploaded. Exact important-file sizes, hashes and restoration
limits are in
[local-only-artifacts.json](../reports/day2-checkpoint-20261111/local-only-artifacts.json).

## Repository scope and next session

Checkpoint branch: `feature/canine-gait-v2`, existing tracking remote
`origin/feature/canine-gait-v2`. Base HEAD:
`8d3dee57a3e82dcd99853ebdbc6275f57aebc886`. The adapter and its original tests
already exist in that history; this checkpoint adds the temporal model,
exploratory training, review support, annotations, execution records and findings.
Unrelated comparison images, paw-diagnosis work, large archives and stray files
are preserved unstaged. No branch switching, history rewriting or force push.

- **Gait AI:** obtain one rights-cleared side-on clip of a clearly different dog
  with a contiguous, independently reviewed contact/airborne span.
- **Motion Studio:** implement one two-video Evidence Replay interaction that
  aligns selected moments and clearly shows evidence quality/uncertainty.

Maintain roughly equal gait-intelligence and product-development effort during
the sprint. Do not expand the conditional simulator pilot into a new workstream.
