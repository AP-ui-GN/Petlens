# Canine temporal contact experiment

Update: an explicit owner-authorized `exploratory_train_only` mode is now
implemented alongside the unchanged strict default. See the
[S004 unsigned job and signing instructions](../reports/canine-contact-batch-v1/exploratory-train-only/README.md)
and [proposed exploratory policy](EXPLORATORY_CONTACT_POLICY.md). This permits
sparse single-dog fitting with source-movie timing after separate approval;
no owner authorization or real training has occurred. The original strict-mode
workflow described below remains available.

Implemented independently from the architectural description in
[the completed readiness audit](CONTACTVISION_READINESS_AUDIT.md). No
ContactVision source or pretrained weights were copied or downloaded.

`src/petlens_gait/contact_model.py` projects the existing 69 feature channels
to 64 dimensions, adds learned positions, applies two bidirectional Transformer
encoder layers (four heads, feed-forward width 128, dropout 0.1), and predicts
four framewise contact logits. This follows ContactVision's input projection,
learned positional embeddings, temporal attention, and framewise sigmoid head.
The input width, four physical paw meanings, masks and scratch weights are
PetLens adaptations. It uses no image encoder and does not alter RTMPose or the
rule-based gait-event detector.

Inputs have shape `(batch, frames, 69)` and outputs `(batch, frames, 4)` in
`LF, RF, LH, RH` order. CONTACT is 1; AIRBORNE is 0. Windows retain source frame
order and delta-seconds, without interpolation or resampling. Raw scores and
observation indicators remain input channels. The trainer consumes the
adapter's 128-frame windows and never indexes padding as frame -1.

These output channels alone do not prove physical identity. `predict()` requires
an explicit reviewed per-paw identity mask and body-reference mask; it also
checks paw observation indicators and padding. Unmapped A/B records cannot
supply four-paw identity. A sigmoid score is exported for every model channel,
but only `eligible` entries have the necessary input/identity support. A state
is returned only when eligible and the larger state probability meets the
configurable confidence threshold (default 0.8). Otherwise the state is -1.
These probabilities and thresholds are uncalibrated. Use `model.eval()` before
calling `predict()`. Attention uses future frames: this is an offline window
model, not a causal streaming detector. Long-video overlap fusion and gait-event
decoding are outside this first experiment.

The loss selects valid elements before binary cross entropy, so UNKNOWN and
unapproved targets (even NaN placeholders) cannot contribute gradients. A batch
without valid targets is skipped. The loader intersects the adapter's label,
visibility, identity, paw observation and target masks, requiring reason
`valid`. Conflicts, provisional states, unreviewed observations, missing pose
and padded targets remain excluded.

## Real training command, once data is approved

From the repository root:

```bash
.venv-canine-v2/bin/python -m training.train_contact \
  --job training/contact_training_approved_job.json \
  --config training/contact_model_config.json \
  --output-dir outputs/contactvision-canine-v1
```

`training/contact_training_approved_job.json` is an intended future input, not
an existing approved dataset. It must follow the schema documented in
`training/prepare_contact_sequences.py`, with hashed sources, explicit fore/hind
physical mappings, independent reviews and reconciliation, rights/timing
evidence, verified dog identities, provenance groups, splits, and approval.
All four paws need both states in the training cohort. At least one supervised
training dog and one separate supervised validation dog are required; include
separate test dogs for a meaningful locked evaluation. All clips, source hashes,
derivatives and provenance groups of a dog must stay in one split. The existing
partition validator runs before training. Test assignments are recorded but
test tensors are never loaded for optimization or checkpoint selection.

The command rebuilds preparation artifacts in a temporary directory using the
existing hash and review validators; it accepts no arbitrary NPZ label input.
Readiness blockers stop execution before constructing a model or creating the
output directory. Synthetic/TEST-ONLY job markers are rejected; there is no
synthetic training CLI option. S004 V1/V2/V3 drafts are not promoted to ground
truth. Their provisional observation, UNKNOWN observations and Hind A frame-43
conflict remain outside approved training supervision.

Configuration fixes the random seed, CPU thread count, optimizer settings,
batch size, epochs and model dimensions. Deterministic PyTorch operations are
enabled. Reproducibility is within the same software/hardware environment;
cross-version bitwise equality is not promised. `run.json` records configuration,
software versions, code hashes and sequence/source provenance. `metrics.json`
records masked BCE, accuracy, contact TP/FP/FN and eligible coverage for training
and validation. Counts are window-weighted (overlapping frames can repeat),
not independent event metrics. The best validation-loss checkpoint and last
checkpoint include model configuration, channel/paw order, weights, optimizer
state and provenance. `load_checkpoint()` validates the feature contract and
loads with `weights_only=True`. CLI resume is not implemented.

## Validation and current status

The existing `.venv-canine-v2` environment supplies PyTorch 2.5.1+cpu. Default
system Python lacks torch; no dependencies were installed. The optional
`requirements-training.txt` remains unchanged. No checkpoint was downloaded.

```bash
.venv-canine-v2/bin/python -m pytest -q \
  tests/test_contact_model.py tests/test_contact_features.py \
  tests/test_s004_contact_draft.py tests/test_s004_contact_draft_v2.py \
  tests/test_s004_contact_draft_v3.py
```

Result: 99 passed. Tests exercise real adapter-to-model tensor compatibility,
forward and backward execution, parameter updates, checkpoint equality after
reload, padding isolation, mapping/abstention, supervision exclusions, timing
and identity boundaries, reproducibility, and dog/group/hash split leakage.
Synthetic tensors and weights are explicitly TEST-ONLY and restricted to
memory/pytest temporary directories. Their metrics are not canine evaluation
results. Running the real CLI against `contact_sequence_inspection_job.json`
also correctly exited 2 with approval/identity/rights/timing/label blockers and
no training output.

The existing `tests/test_gait_event_review.py` suite also passed all 49 tests.
Its four local HTTP tests initially encountered sandbox socket restrictions;
the full suite passed when rerun with permission outside the sandbox.

Work started on branch `feature/canine-gait-v2` at
`8d3dee57a3e82dcd99853ebdbc6275f57aebc886`, with pre-existing modified and
untracked files. This implementation adds only the model, trainer, configuration,
tests and this document. Existing videos, predictions, annotation versions,
RTMPose, the baseline and unrelated edits were left intact. No commit or push
was performed.

Model code is implemented and synthetic execution works. No real canine
contact model has been trained; real-world contact accuracy is unvalidated.
The next action is to produce an independently reviewed, reconciled and
approved canine training cohort with verified paw mappings and dog splits.
