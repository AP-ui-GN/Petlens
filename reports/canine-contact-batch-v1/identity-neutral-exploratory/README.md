# Front C: identity-neutral exploratory experiment

Anatomical side remains **UNKNOWN**. The local source-frame contact sheet and
camera metadata do not establish a trusted anatomical reference linking the
reviewer's C to left or right. V3's C description says nearer the head at an
unspecified stationary reference, explicitly leaving anatomy unverified.
No screen-position or AP-10K-channel guess has been made.

One additional linear readout consumes the existing Transformer encoder's
representation. Its single output means **this Front C, in S004, frames 46–50**,
bound to source-video hash, dog grouping and dataset. It is neither LF nor RF,
and never represents Front D or 'either front paw'. No anatomical logits are
combined or selected by loss. The original anatomical head is frozen and unused;
the existing model code, adapter, strict pathway and old checkpoints are intact.
New auxiliary checkpoints have a distinct format and loader:
`petlens_gait.contact_identity_neutral.load_neutral_checkpoint`.

This is clip-bound fitting. There is no physical-paw localization/selection
mechanism for an arbitrary new clip. It can memorize frame phase or whole-body
pose correlations. A successful fit would not prove reliable temporal contact
recognition, anatomical mapping, generalization or clinical validity.

## Real observations prepared, not approved

- C46: CONTACT, approximately 80% reported confidence.
- C50: AIRBORNE, 100% reported confidence.
- Same physical paw through 46–50: confirmed by the requesting human in this
  task, recorded separately in `reviewer-physical-continuity.json`.
- Anatomical side: UNKNOWN; reviewer exposure remains `prior_exposure`.
- Only these two observation approvals are requested. C47–49 remain unreviewed
  contact states and cannot supervise. A43, D13 and all other uncertain states
  remain excluded. Confidence is retained as evidence, not a loss weight.

The original V3 sidecar supplies labels and endpoint visibility. The new report
does not rewrite V3 or pretend to be independent truth or owner authorization.
Both AP-10K front observation channels must be valid at supervised frames,
alongside the human physical continuity report and valid body reference. This
conservative quality check does not establish anatomical correspondence. No
visibility or contact state is fabricated for the three intervening frames.

## One owner approval checklist

Review `owner-authorization.UNSIGNED.json` and sign only supported assertions:

1. Accept the exposed reviewer under the proposed train-only exception and
   identity-neutral addendum. Set the base scopes and `identityNeutralOutput`
   true, top-level approval/training authorization true, and provide owner
   name, date and evidence. Policy hashes bind the exact reviewed proposal.
2. Individually approve C-frame-46 and C-frame-50 with name/date/evidence.
3. Accept and sign the provided physical continuity evidence for C46–50. No
   anatomical mapping or repeat annotation pass is required; mappings stay null.
4. Accept the documented reuse rights and attribution for this experiment.
   Sign `rights`; only then mark the job's rights status `cleared` with evidence.
   The stored record retains embedded CC BY 3.0 and Commons CC BY 2.5 notices
   and their discrepancy. This implementation grants no rights clearance.
5. Confirm/sign dog and source grouping. The job conservatively groups related
   S003/S004 material; it does not assert different dogs. Set the job's
   `dogIdentityVerified` and `trainingApproved` true only after this approval.
6. Acknowledge that this single-dog, train-only run establishes no independent
   validation, generalization accuracy, accurate event timing or clinical result.

Both policies are proposals: [base policy](../../../docs/EXPLORATORY_CONTACT_POLICY.md)
and [identity-neutral addendum](../../../docs/EXPLORATORY_IDENTITY_NEUTRAL_POLICY.md).
The project-imposed independent-review requirement remains intact in strict
mode. No signature or approval was granted by the assistant. The job is blocked
until these explicit authorizations exist; do not run if reuse is impermissible.

After signing, update the hash of the authorization file in `training-job.json`:

```bash
python - <<'PY'
import hashlib, json
from pathlib import Path
folder = Path('reports/canine-contact-batch-v1/identity-neutral-exploratory')
path = folder / 'training-job.json'
job = json.loads(path.read_text())
ref = job['sequences'][0]['exploratoryApproval']
ref['sha256'] = hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest()
path.write_text(json.dumps(job, indent=2) + '\n')
PY
```

Hash refresh grants no approval. Changed observations or source files require
new hashes and owner authorization; V1–V3 must remain unchanged.

## Command after authorization

```bash
.venv-canine-v2/bin/python -m training.train_contact \
  --job reports/canine-contact-batch-v1/identity-neutral-exploratory/training-job.json \
  --config training/contact_identity_neutral_config.json \
  --output-dir outputs/contact-s004-physical-c-v1
```

The prepared config requests five epochs, batch size one and fixed seed. With
approval, the proposed span supplies one five-frame training window padded to
128, with two supervised positions on one physical output and zero anatomical
targets. There is no validation split or best-validation checkpoint. Outputs
are training-only metrics, provenance and `last.pt` with explicit physical
binding and unvalidated exploratory metadata. No real training has occurred.
