# Human paw annotation preparation

This offline pipeline prepares human physical-paw references and **partial AP-10K
COCO annotations** for future RTMPose-m fine-tuning. It does not train, run pose
inference, or use model predictions as ground truth. Only Python's standard
library and the existing OpenCV installation are required.

Run from the repository root, using a new output directory:

```bash
python -m training.prepare_paw_annotations --output-dir reports/paw-annotation-data-v1
python -m unittest discover -s tests -p test_paw_annotation_data.py -v
```

`training/paw_annotation_sources.json` pins SHA256 hashes of the existing videos,
prediction JSON, annotation exports, source manifests and repository keypoint
schema. Inputs include locally cached files under ignored `tmp/`; this is not a
self-contained downloadable dataset. Missing or changed sources fail explicitly.
The Dalmatian original and inference derivative are both hashed. Frames are
decoded from the verified inference-source videos, with dimensions, frame count,
FPS and timestamps checked against the saved metadata. No overlays are used.

## Output contract

| File | Purpose |
|---|---|
| `physical-reference.json` | Deduplicated human A/B labels, source references, frame times and original prediction context in separate fields. |
| `original-annotations.json` | Original parsed exports, preserving annotator, exposure, events, continuity and other fields. Input files remain unchanged. |
| `images/{dalmatian,dog02}/*.png` | Lossless frames decoded from verified videos; hashes are recorded. Images are locally generated and git-ignored. |
| `anatomical-review-template.json` | Per-frame A/B anatomical review queue; all anatomical channels initially null. |
| `accepted-anatomical-reviews.json` | Explicit human anatomical decisions supplied to this build, if any. |
| `train.coco.json` | Dalmatian images and only anatomically reviewed human point targets. |
| `exploratory_evaluation.coco.json` | dog02 equivalents; never training or model selection. |
| `manifest.json` | Input/output hashes, builder hash, OpenCV version, split membership, deduplication counts and excluded-target reasons. |

Physical A/B is **not** anatomical left/right, image side, or a model channel.
Human coordinates are retained even if the model is inaccurate, low confidence,
or missing a candidate. No distance threshold, confidence threshold, nearest-point
matching, interpolation or automatic anatomical mapping is used.

The source annotation schema is `physical-hind-tracks`, version 1. `visible`
requires a finite in-image human coordinate. `occluded`, `uncertain`/`ambiguous`
and `unmarked` require null coordinates. These states remain distinct in the
physical reference. Identical completed paw labels are deduplicated; an unmarked
placeholder cannot erase a label. Conflicting completed labels or metadata fail
rather than silently choosing an export. JSON duplicate keys also fail.

## Anatomical review and future fine-tuning

Copy the generated review template to a separate human-edited file. For each
visible point you can anatomically verify, set `anatomicalKeypoint` to
`left_back_paw` or `right_back_paw`, with `reviewer` and a concrete `evidence`
description. Review original images and adjacent frames. Do not fill a global
"A=left" assumption or use RTMPose label names to decide. Leave unresolved
entries null. Label/image hashes bind every review to its exact reference.

```bash
python -m training.prepare_paw_annotations \
  --anatomical-reviews /path/to/human-reviewed-anatomy.json \
  --output-dir reports/paw-annotation-data-reviewed
```

Exported COCO targets use the repository's AP-10K 17-channel order. Only reviewed,
visible human points get `(human_x, human_y, 2)`. All other channels use COCO's
unlabeled `[0, 0, 0]` sentinel: **these zeros are not coordinates or negative
location targets**. The future RTMPose/SimCC training configuration must mask
their loss weights. There are no front-paw, hip or knee targets unless humans
annotate them through a future schema extension. The current exporter never
substitutes those predictions for labels.

An occluded state alone has no location target. A partially hidden pose can use
an existing visible point only where the reviewer can actually locate the paw.
Training on human-inferred occluded locations (`v=1`) would need an explicit new
annotation schema for those human coordinates and their uncertainty; it is not
enabled by this builder. Do not guess fully hidden coordinates to fill the file.

COCO `bbox` currently describes the full frame, not a human dog-box annotation.
This avoids cropping away corrected points. Review dog crops before a useful
top-down experiment; a saved detector box may provide a proposal but is not a
verified label. The output uses the dataset root as `data_root` and relative
`file_name` paths. Its COCO layout is prepared; an installed MMPose loader and
RTMPose training configuration have **not** been exercised here.

The existing `training/train_pose.py` trains a separate ResNet heatmap model; it
is not the RTMPose fine-tuning entry point. A future RTMPose run needs the matching
trainable pretrained checkpoint and configuration. The cached inference ONNX file
is not a drop-in training checkpoint. No weights were obtained in this task.

## Inventory and first experiment

| Source | Stored frames | Frames with visible labels | Visible physical points | Occluded slots | Unmarked slots | Anatomical targets now |
|---|---:|---:|---:|---:|---:|---:|
| Dalmatian, training | 46 | 42 | 79 | 10 | 3 | 0 |
| dog02, exploratory evaluation | 29 | 28 | 55 | 1 | 2 | 0 |
| Total, deduplicated | 75 | 70 | 134 | 11 | 5 | 0 |

Six repeated dog02 A labels were removed. No new human coordinate is required to
retain the 134 existing visible physical references. **None can currently be
assigned directly to an anatomical AP-10K output channel.**

Minimum practical next annotation pass: anatomically adjudicate the **79 existing
Dalmatian points across 42 frames** you intend to train on, confirming a consistent
paw landmark and reviewing crops. Anatomically adjudicate the **55 dog02 points
across 28 frames** before evaluating left/right localization there. Unresolvable
points stay unlabeled; these counts are a review queue, not a required statistical
sample size or permission to force identity. Review crossings and partial
occlusions explicitly. Front paws and major joints need additional human point
labels before those channels can be fine-tuned or evaluated.

After review, start with a small masked hind-paw localization fine-tuning pilot
of the existing RTMPose-m, using Dalmatian only and a fixed training schedule.
First verify on a few reviewed frames that coordinate transforms and masked
losses work. Compare saved-pretrained and subsequently fine-tuned localization
against the same human coordinates; retain difficult points even if pretrained
predictions miss them. dog02 remains exploratory reporting only, never checkpoint
selection or hyperparameter tuning.

The present single training sequence supports a technical feasibility/overfit
check, not a generalization result. Meaningful model selection additionally needs
a separately reserved, anatomically annotated development sequence; none is
available under the current split policy. No defensible minimum video count for
generalization follows from this inventory. Further gait-event/stride claims need
their own temporal identity and event validation and are outside this dataset.

## Browser review mode (V2)

From the repository root, using the Python environment with the existing OpenCV
installation:

```bash
python -m training.review_paw_annotations --port 8765
```

In Codespaces, open the **Ports** panel, forward port **8765** if necessary, and
choose **Open in Browser**. Keep the port private. Add `/?dataset=dalmatian` to the
forwarded origin:

```text
https://<codespace-name>-8765.app.github.dev/?dataset=dalmatian
```

Locally use `http://localhost:8765/?dataset=dalmatian`. For exploratory dog02
review use the same origin with `/?dataset=dog02`. The source videos, saved
predictions and source annotations must already exist at the paths in
`training/paw_annotation_sources.json`. Startup verifies their hashes. No model,
training job or download runs. Video decoding uses the existing OpenCV dependency;
the server and export validator use the Python standard library.

This launcher serves the existing `tmp/rtmpose-test/paw-tracking-experiment/manual-annotation/`
HTML, CSS, canvas, coordinate scaling, frame navigation and playback. It injects
`training/paw-review.js` as a review mode without modifying the original interface
files or original browser annotation storage. The new launcher and extension live
outside ignored `tmp/`, so they can be included in a later commit.

Manual pass:

1. Start with **Dalmatian: 79 visible points in 42 frames**, already loaded into
   the default queue. A/B remain physical identities. Each frame has independent
   anatomical decisions; selecting one paw never assigns the other automatically.
2. Use neighboring-frame buttons or **All frames: continuous context** and slow
   playback to follow the connected hind leg through crossings. Anatomical left
   and right are the dog's sides. Choose **Uncertain** when anatomy or continuity
   cannot be resolved. Do not use RTMPose label names to decide identity.
3. Select physical **A** or **B** and click to correct the visible paw-tip location
   in the original pixel space. Original and current coordinates appear side by
   side. Confirm that the same visible paw-tip landmark is used consistently and
   that the physical paw was followed through temporal context. A coordinate or
   visibility edit resets that paw's anatomical verification and both confirmations.
4. For each verified point, select anatomical left/right hind, check both
   confirmations, enter your reviewer ID and specific anatomical evidence/context
   frames. Corrections also need reviewer ID and a reason, even if anatomy remains
   uncertain. These confirmations are human assertions, not automated validation
   of anatomical truth. Consecutive verified observations of the same physical
   track cannot assert opposite sides; mark unresolved tracking breaks uncertain.
5. **Reveal saved predictions** optionally overlays explicitly marked model crosses
   on the current frame and records model exposure. Predictions are audit context;
   their coordinates and left/right names never populate human targets.
6. Download **draft JSON** regularly; drafts can contain incomplete work and can be
   resumed using **Resume draft**. Browser autosave is separate from the original
   annotations and is shared between the two review datasets in the same browser.
7. **Validate & download versioned export** downloads a timestamped V2 ZIP. Invalid
   or conflicting verified assertions block the export with an error. Leave
   unresolved entries unreviewed/uncertain with no anatomical channel. They remain
   in the review and physical reference, but produce no anatomical target.

The ZIP contains the editable `review.json`, original and corrected physical
references, separate `train.coco.json` and `exploratory_evaluation.coco.json`, and a
manifest with source video/prediction/annotation hashes, reference hash, exporter
hash and SHA-256 hashes of every payload. Original frame-image hashes and original
label hashes bind decisions to provenance. Only verified, visible, explicitly
confirmed human coordinates enter COCO; no complementary paw, model point or hidden
coordinate is inferred. dog02 stays exploratory and cannot enter the training file.

The ZIP does not duplicate video or frame images. COCO image paths refer to the
existing `reports/paw-annotation-data-v1/images/` tree; use that directory as the
image root (or copy its `images/` beside extracted COCO files). V2 `review.json` is
for this review mode; do not pass it to the older V1 `--anatomical-reviews` option.
No export overwrites source files or changes the prepared V1 dataset. This review
work does not establish any anatomical target until a human completes the pass.

Checks:

```bash
python -m unittest tests.test_paw_review tests.test_paw_annotation_data -v
node tests/test_paw_review_ui.cjs
```

The Node test exercises the actual existing scripts plus the extension with a DOM
simulation for both datasets; it does not assert browser geometry. Check canvas
fit, click alignment and playback in the Codespaces browser during manual review.

Dalmatian bulk anatomical mapping is available in review mode for source frame
indices **46–90 inclusive**: A = right hind, B = left hind. Choose **Preview affected
frames and counts** to see each eligible frame, paw, annotation count and exclusion.
The preview does not change labels. Enter a reviewer ID and anatomical evidence,
check the explicit landmark/continuity/mapping confirmation, then choose **Apply
confirmed human mapping**. Changes to the draft require a fresh preview.

Propagation requires both physical tracks to be continuous (or `start` at
46), using source annotations or the separately recorded reviewer evidence. Missing/unreviewed/broken continuity, identity conflicts, and ambiguous or
uncertain identities stop propagation for the remaining range. This deliberately
does not bridge a gap using later `continuous` labels. The original source has unreviewed continuity beginning at 75. The user
confirmed physical A/B continuity for frames 75–90; this statement is stored in
`training/paw_bulk_continuity_evidence.json`, bound to the reference hash, as
**reviewer-provided, not independently verified**. It fills unreviewed continuity
only and cannot override explicit breaks, swaps or uncertainty. Source continuity
records remain unchanged. An untouched draft now previews **42 frames / 79 visible
annotations** in 46–90. The 11 nonvisible slots remain excluded: B at 61; A at
81 and 83; both at 84, 86 and 87; B at 85 and 88. These require manual attention
only if additional targets are desired; occluded points are not inferred. Existing human decisions,
corrections, evidence, and confirmations are preserved as well.

Apply updates only the local review draft. **Validate & download versioned export**
saves the mapping in `review.json` as `human-confirmed-mapping`, with reviewer,
evidence, confirmation time, exact targets, exclusions, reviewer-provided continuity evidence, and pre-assignment review
labels. The ZIP also includes `validation.json` listing missing visible identities
and nonvisible slots; missing physical slots, duplicate assignments, and conflicting
identities cause validation to fail. Apply validates the resulting draft before returning it. Export validation independently recomputes eligible targets. Original
physical annotations remain in the ZIP and source files are never changed. Manual
edits detach an entry from its bulk provenance while preserving the operation audit.

Generate a read-only preview without starting the UI or applying labels:

```bash
python -m training.review_paw_annotations --preview-output reports/paw-bulk-mapping-preview.json
```

Use `--draft path/to/review.json` to include saved anatomical decisions and
uncertainty. Without it, counts use the original annotations; browser autosaves
are accessible only within the UI. The preview includes every eligible coordinate,
proposed anatomical identity, continuity source, exclusion, and current validation
report. All labels remain unassigned until the reviewer explicitly confirms the
preview in the UI.

If preview reports missing reviewer/evidence, choose **Check incomplete reviews**.
It checks the current browser draft and lists every incomplete review by dataset,
frame, physical paw and missing field. The bulk reviewer/evidence inputs apply
only to new bulk assignments; they cannot fill provenance for existing decisions
or coordinate edits. Complete those records using the actual review information.
The check and **Download validation report** do not change or reset any labels.
Do not replace the current browser draft with a newly seeded draft to clear errors.

For a downloaded draft, the same read-only check is available without the browser:

```bash
python -m training.review_paw_annotations --draft path/to/review.json --diagnostics-output reports/review-diagnostics.json
```

The diagnostics path must be new. A valid draft may still have unreviewed points;
passing export validation does not constitute human confirmation of a proposed
mapping. The original physical annotator is not automatically the anatomical
reviewer. Continuity evidence remains scoped to its recorded claim.

The user subsequently explicitly confirmed the reviewed Dalmatian mapping and
authorized reusing their mapping and continuity statements as reviewer-provided
evidence. This is recorded in `training/paw_anatomical_mapping_confirmation.json`.
The reviewer is identified only as `requesting user` (conversation participant);
no personal name or independent anatomical observation is asserted. This allows
direct export without repeating the browser review:

```bash
python -m training.review_paw_annotations --mapping-confirmation training/paw_anatomical_mapping_confirmation.json --export-output path/to/new-export.zip
```

Use `--draft` when a saved V2 review exists. Without it, the command uses on-disk
physical annotations and refuses to ignore nonempty accepted V1 anatomical
reviews. Browser-only drafts are unavailable, unmodified and explicitly outside
the export's input scope. Existing edited, verified and uncertain records are
preserved; missing provenance still fails validation. Conflicting or uncertain
decisions that prevent the confirmed 79 points / 42 frames block export instead
of being overwritten. The ZIP path must be new. Every source coordinate and
visibility value stays unchanged. The export stores the user's statements and
continuity evidence in its review audit and manifest-hashed payloads.
