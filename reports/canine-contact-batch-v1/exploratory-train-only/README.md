# S004 exploratory train-only job

Implementation complete; owner authorization is UNSIGNED. No real training has
occurred. The unsigned real command correctly exits 2 before model construction
or output creation: `Exploratory owner authorization missing or unsigned`.

The proposed [policy](../../../docs/EXPLORATORY_CONTACT_POLICY.md) is separate
from strict mode. Two independent unexposed reviewers are a project protocol,
not an external requirement identified in project records. This proposal permits
the existing honestly exposed human's sparse observations only after explicit
owner authorization. It confers no independent validation status.

## Human actions required

Edit `owner-authorization.UNSIGNED.json` only when the evidence supports it:

1. The owner signs the top-level reviewer/date/evidence, role `project_owner`,
   `approved=true`, `trainingApproved=true`, and each policy scope. Keep the
   policy and input hashes bound to the actual reviewed files.
2. Sign `dogIdentity` with source/dog continuity and conservative grouping
   evidence. Keep S003/S004 related footage in the same training/provenance
   group. In `training-job.json`, set `dogIdentityVerified=true` only after that
   verification. This does not assert S004 is a different dog from S003.
3. Confirm rights for this use, retain the existing license-version discrepancy
   and attribution, and sign `rights`. Change the job's rights status from
   `attribution_required` to `cleared` and record the clearance evidence only
   after that human decision. The existing rights/source records are unchanged.
4. Supply a signed anatomical mapping for each supervised physical paw. The
   form lists A/B as hind, C/D as front; anatomical assignments are null.
   For the minimal experiment only C needs mapping to LF or RF, supported by
   human anatomical evidence. Unmapped paws remain unsupervised. AP-10K output
   confidence and screen position do not establish this mapping.
5. Using the existing reviewer, check Front C at frames 46–50. Sign the proposed
   visible-continuous identity span only if supported, changing
   `visibleContinuous` to true. This certifies identity/visibility, not contact
   state on frames 47–49; their contact targets stay masked.
6. Individually sign the existing candidate observations to be used. The
   smallest proposed selection is C-frame-46 CONTACT and C-frame-50 AIRBORNE.
   These remain reports until human approval. Leave the other approvals false
   if not individually authorized. Corrected labels must be saved as a new
   source-bound version, with new hashes and authorization, never by overwriting
   V3. The importer masks disputed/provisional/UNKNOWN/unreviewed assertions
   regardless of an accidental approval request.

There are **10 potentially usable conflict-free definite assertions** (7 CONTACT,
3 AIRBORNE) and **zero currently approved labels**. A43 is excluded; D13 stays
provisional. No fresh independent reviewer is required under the proposed
exploratory policy once the owner explicitly authorizes it. Strict mode still
requires its original two independent reviewers and reconciliation.

Open the existing reviewer; no new annotation interface is needed:

```bash
python -m training.gait_event_review \
  --dataset gait-s004 \
  --manifest reports/canine-contact-batch-v1/frame-manifest.json \
  --port 8767
```

Keep the original reviewer/exposure declaration. New reviews or resolutions
must be separate files. All V1–V3 records are preserved.

After signing the authorization file, refresh its hash in the job. This step
only seals the edited file; it grants no approvals:

```bash
python - <<'PY'
import hashlib, json
from pathlib import Path
folder = Path('reports/canine-contact-batch-v1/exploratory-train-only')
job_path = folder / 'training-job.json'
job = json.loads(job_path.read_text())
record = job['sequences'][0]['exploratoryApproval']
record['sha256'] = hashlib.sha256(Path(record['path']).read_bytes()).hexdigest()
job_path.write_text(json.dumps(job, indent=2) + '\n')
PY
```

## Exact execution command after authorization

```bash
.venv-canine-v2/bin/python -m training.train_contact \
  --job reports/canine-contact-batch-v1/exploratory-train-only/training-job.json \
  --config training/contact_exploratory_config.json \
  --output-dir outputs/contact-s004-exploratory-v1
```

Configuration: five epochs, batch size one, fixed seed, CPU, existing small
Transformer. The output directory must not exist. Up to 32 supervised windows
and 100 epochs/3,200 steps are enforced. A minimally approved C46–50 span gives
one five-frame window with two supervised endpoint observations, padded to 128.
No per-frame contact interpolation occurs.

Outputs are `run.json`, training-only `metrics.json`, and `last.pt`, with policy,
code, source and authorization hashes, honest review exposure and unvalidated
exploratory flags. There is no validation metric, best-validation checkpoint,
test evaluation, or event-timing accuracy claim. A successful fit demonstrates
optimization on this dog only, not a reliable contact detector.

## Verification

124 focused tests passed across exploratory mode, model, feature adapter and
S004 V1–V3 preservation. Synthetic fixtures exercise signed/unsigned approvals,
single-dog/partial-paw execution, masked excluded states, movie timing, strict
mode separation, training loss decrease, nonzero gradients, parameter updates,
bounds and exact checkpoint reload. All synthetic artifacts are TEST-ONLY in
pytest temporary directories; the real trainer rejects synthetic job markers.
The actual unsigned S004 command was checked and rejected before output creation.
No real canine training was performed. Existing source/model/annotation hashes
were checked unchanged, except the intentionally modified preparer and trainer.
