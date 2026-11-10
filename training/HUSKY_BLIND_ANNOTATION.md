# Blind Husky evaluation annotation

Use the existing paw-review application, its canvas, A/B marker controls and
frame navigation. Husky is an isolated dataset option, with separate browser
storage and human exports. No Husky labels enter Dalmatian/Dog02 references,
training COCO files, or `paw_annotation_sources.json`.

Start from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m training.review_paw_annotations --port 8766 --husky-manifest reports/husky-evaluation/annotation-manifest-v1.json
```

Open **http://localhost:8766/?dataset=husky-evaluation**. In Codespaces, forward
port 8766 in VS Code's Ports panel and append `/?dataset=husky-evaluation` to its
forwarded URL. The existing Dalmatian and Dog02 links remain available.

## Verified package and frame-count discrepancy

The input package is
`tmp/petlens-husky-evaluation/PetLens_Husky_Evaluation/`.
Preparation created the separate
`reports/husky-evaluation/annotation-manifest-v1.json`; original package manifests,
PNGs and video were preserved.

All **20 sampled PNGs** match their sequentially decoded prepared-video frames
**pixel for pixel**, at **1228×754**, with matching timestamps within 1ms.
The video and input manifests are bound by SHA256; each sampled image has a byte
hash and every decoded frame has a pixel hash. Startup reverifies the package
before serving any frames.

The preparation text says source recording frames **39–102 inclusive**, which
implies **64** frames. The MP4 container also advertises **64**, while sequential
decoding yields **63**, matching the preparation manifest's declared count.
The new manifest records all four observations under `frameCountDiscrepancy`.
Annotation uses prepared-video indices **0–62** and actual decoded timestamps.
The original screen recording is unavailable in this package, so which original
source frame is absent remains unresolved. No source-index offset/gap is guessed.
These screen-record timestamps do not validate native gait timing or gait cycles.

To regenerate verification into a fresh manifest if needed:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m training.blind_paw_annotations --output-manifest reports/husky-evaluation/annotation-manifest-recheck.json
```

Existing manifests cannot be overwritten. The standard library and the already
installed OpenCV/NumPy suffice; no models, inference or downloads are involved.

## Human workflow

1. Enter your reviewer ID. Choose **Physical A** or **Physical B**, then click a
   visible hind-paw tip. A/B do not predefine anatomical sides. Coordinates are
   saved in original image pixels even when the canvas is scaled.
2. Use visibility **occluded**, **uncertain** or **ambiguous** when no reliable
   coordinate can be placed. Those states retain null coordinates. **Unmarked**
   means not reviewed; it is not silently converted into an occlusion.
3. A visible point may separately have **Uncertain** anatomical identity and keep
   its coordinates. Do not force left/right. Only assert an anatomical side when
   human evidence supports the paw-tip landmark and physical continuity; record
   that evidence and check the two confirmations. No bulk mapping is offered.
4. The selected queue contains the 20 samples. **All 63 prepared frames** and
   neighboring-frame buttons provide original context; unsampled frames cannot
   receive annotations. The model-reveal controls are unavailable, and the
   Husky prediction API returns HTTP 403. Blind startup does not load the legacy
   prediction session.
5. **Download draft backup** saves resumable JSON. Autosave uses a Husky-specific,
   manifest-bound browser key; existing review drafts are preserved. **Resume
   Husky draft** rejects foreign, stale or model-exposed labels.
6. **Validate, save & download versioned evaluation export** validates the human
   draft, writes a new ZIP under **`reports/husky-evaluation/annotations/`**, and
   downloads it to the browser. Its unique timestamp/ID filename prevents
   overwrite. The page displays the server-side path.

Exports contain `review.json`, `frame-manifest.json`, `validation.json`, and a
hashed `manifest.json` with reviewer, UTC creation time, source-manifest hash and
exporter hash. They contain **no training COCO export**. Partial/unreviewed and
uncertain labels are retained explicitly; export does not claim the 20 frames
were completely reviewed or anatomically verified. Physical A/B continuity
through gaps remains a human review question, not an inferred label.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_blind_paw_annotations.py -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_paw_review.py -v
PYTHONDONTWRITEBYTECODE=1 node tests/test_blind_paw_review_ui.cjs
PYTHONDONTWRITEBYTECODE=1 node tests/test_paw_review_ui.cjs
```

The backend tests include a temporary localhost HTTP server. UI tests exercise
the real shared JavaScript in a minimal DOM; they do not substitute for a full
browser usability review. Real package verification established pixel/time
alignment independently of those synthetic tests. No human labels have been
created by the preparation step.
