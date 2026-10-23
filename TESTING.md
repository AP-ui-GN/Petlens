# Testing guide

## Automated checks (verified)

From the workspace root, with the project `.venv` activated for Python:

```bash
pnpm run typecheck
pnpm build
pnpm --filter @workspace/api-server run test
python -m unittest discover -s tests -t .
```

What those cover:

- TypeScript across libs, API, and the app
- Production builds of the API and the frontend
- API tests, including multipart parsing, the upload gate, explanation
  validation, phone walk helpers, and the AI-use registry (45 passed / 0 failed
  on October 22, 2026)
- Motion statistics, gait metrics, keypoint-schema checks, dog-box association,
  the local setup check, confidence gating, and clip-quality notes (96 passed /
  0 failed on October 22, 2026)
- Uploaded clips are deleted after `POST /api/analyze`, including when the
  file is rejected (`tests/upload-cleanup.test.ts`)
- Pet-form validation and trend grouping, from the web package:

```bash
pnpm --filter @workspace/silverpaws-beta run test
```

Standalone pipeline (no API):

```bash
python scripts/analyze_clip.py path/to/walk.mp4 --pet-name Mabel
```

Add `--no-pose` to force the OpenCV-only path.

Pull requests into `main` run `.github/workflows/tests.yml`. That job installs `requirements-opencv.txt` only. It does not download pose weights, and it does not treat a skipped model run as a pass. `python scripts/check_setup.py` reports whether weights are already on disk and exits 0 when OpenCV imports.

Dog-box association is `gait_engine/tracking.py`. A zero-overlap box does not keep the previous identity, a short gap stays empty, and a long gap starts a new segment. Those cases are synthetic boxes in `tests/test_tracking.py`. They do not measure stride length.

Pose review images (not a validation, and not committed):

```bash
python scripts/check_pose_backend.py path/to/dog-walk.mp4 --out outputs/pose-check/
```

The script labels each point with the checkpoint's COCO joint name. See
`docs/pose-validation.md` and `docs/MODEL_CARD.md`.

## Live product checks (verified in this pass)

Both services running:

```bash
pnpm --filter @workspace/api-server run dev
pnpm --filter @workspace/silverpaws-beta run dev
```

### Pet profile

- Create a pet named Mabel and save — profile appears in the device list
- Data is in `localStorage` key `silverpaws:pets`

### New analysis

- Choose a short MP4 and review it
- Run analysis — processing stage, then history detail
- Result includes overall score, factor breakdown, raw measurements, and
  limitations (not a diagnosis)
- Non-video upload to `/api/analyze` returns 400
- Missing file returns 400 “Choose a video file…”
- Corrupt `.mp4` returns 400 “could not be opened as a video”

### History and report

- Detail page separates **raw measurements** from **interpretation**
- PDF contains those sections in that order, plus source/license fallbacks
  and “not a medical diagnosis”

### Safety

- Footer shows the disclaimer and emergency note on every page
- A large drop vs the previous walk, or reliable high asymmetry, sets
  `concerningChange` and tells the owner to ask a veterinarian

## What to test

On a saved result, the AI-use lines should name only the steps that produced that walk: the dog detector and the pose model when pose ran, frame-to-frame motion (it runs on every clip), fixed scores and a fixed note, and a language-model reword only when the server kept one.

## Manual checklist (for teammates)

- [ ] Create and edit a second pet
- [ ] Reject a huge file in the UI before upload
- [ ] Run two clips for the same pet and confirm the second observation
      mentions the score difference
- [ ] Delete an observation and visit its old URL
- [ ] Stop the API and confirm the analyze page shows a reachable-service error
- [ ] Confirm the COCO-17 pose-output path (`pipeline: "coco-pose"`) on a machine with
      the CPU torch stack from `requirements.txt`

## Pet form and trends (automated)

```bash
pnpm --filter @workspace/silverpaws-beta run test
```

That command covers:

- pet form: a blank name is not valid, so the page does not save
- pet form: age or weight that is present but not a positive number is rejected
- pet form: a blank age and weight, with a name, can be saved
- history trends: an empty list produces no series
- history trends: walks from different pipelines stay in separate series
- history trends: a missing score stays null and is not drawn as zero

The history page still shows the empty-state “Record a walk” link when no
walks are saved (`data-testid="link-history-start-analysis"`). That screen is
not browser-automated here.

## Optional language-model rewrite

`pnpm --filter @workspace/api-server run test` covers three provider cases with
a mock `fetch`:

- no `SILVERPAWS_LLM_*` variables → rule-based text, `usedLlm: false`
- a rewrite that only quotes measured values → that text, `usedLlm: true`
- a rewrite that invents a number → discarded, rule-based text shown, `usedLlm: false`

A live clip with a real provider was not run. No endpoint was configured.

Existing browser test (Chromium on Replit):

```bash
node artifacts/silverpaws-beta/tests/report-download.browser.mjs
```

That test expects `CHROMIUM_PATH` and is not required for a local Windows run.

## validation_clips

That folder is gitignored, so a README inside it would not be kept. Add clips
and `labels.csv` there when you have them. Columns are
`file,label,source,license,notes`. `label` is `normal`, `mild`, or
`significant`. Do not commit the videos.

```bash
python scripts/validate_gait.py --clips-dir validation_clips \
  --labels validation_clips/labels.csv --out outputs/validation.csv
```

If the folder is empty the command prints how to add clips and exits 0.
Its summary line says the result is preliminary, a small sample, and not
clinical validation.

## What is not tested here

- A production deployment and memory measurement on the hosting provider. The hosted Docker image build and synthetic API smoke test passed in GitHub Actions on October 22, 2026 (see [container-smoke run](https://github.com/AP-ui-GN/Silver-Paws-AI/actions/runs/39818601906)).
- Live LLM provider (the request is unit-tested with a mock; no live endpoint was configured)
- `lib/db` — unused in the beta

## Phase 6 record (October 18, 2026)

Checks that passed in this environment:

- `python -m unittest discover -s tests -t .` — 55 passed
- `pnpm --filter @workspace/api-server run test` — 35 passed
- `pnpm --filter @workspace/silverpaws-beta run test` — 9 passed
- `pnpm run typecheck` — passed
- GitHub checks on pull request 1 — `gh pr checks` reported no checks on this branch. None were failing because none were reported.
- Workspace lint — there is no lint script and no ESLint config. That command was not run, and it is not recorded as passed. Typecheck is the static check this repo has.
- No `SILVERPAWS_LLM_*` variables were set. `POST /api/analyze` of a synthetic clip returned `usedLlm: false`.
- Mock provider, from `artifacts/api-server/tests/explanation.test.ts`: a valid rewrite sets `usedLlm: true`; an invalid rewrite is discarded and the rule-based note stays (`usedLlm: false`).
- Low-confidence keypoints, from `tests/test_model_phase.py`: confidence 0.1 is not trusted, `framesUsed` is 0, and the summary is not treated as missing. A missing score is the words "Not measured" or "Not scored", not zero (trend tests, report test).
- Non-video upload: `POST /api/analyze` with `notes.txt` returned 400, "That file is not a video PetLens can read. MP4, MOV, and WebM work best."
- Oversized upload: the server was started with `MAX_UPLOAD_MB=1` (the default in code is 60). A body over that cap returned 413, "That clip is larger than the 1 MB beta limit. Try a shorter clip."
- OpenCV was attempted. A generated moving rectangle (not a pet, and not a file from the repo) was analyzed with `analyze_clip(..., use_pose=False)` and again through `POST /api/analyze`. Both returned `pipeline: "opencv-motion"`, `aiUse: ["motion-fallback", "scoring", "observation-rules"]`, and null stride symmetry. The same file with pose requested also returned `opencv-motion`, because TensorFlow is not installed.
- The screen lines for that `aiUse` list, from `aiUseResultLines`, are the registry sentences for motion, scoring, and rules. `development` is not included. The web screen was not opened for that list, so the pixels were not compared.

Checks that were not run, and are not passed:

- UI → API → pipeline with a real walking clip. The repository has no `.mp4`, `.mov`, or `.webm`. No browser was used for a real walk.
- A full labeled pose validation. See the clip folder note below.
- The low-confidence banner on a real walk in the browser. The banner code is in the walk-detail screen.
- Server down → the offline note and the kept clip. The API process was stopped and `curl` to it failed. The Analyze screen was not opened. That path was not exercised in a browser.
- Demo mode in the browser. Unit tests drop the sample from history and trends helpers. The Demo screen was not opened.
- A live language-model provider. No endpoint was configured.
- `node artifacts/silverpaws-beta/tests/report-download.browser.mjs` — needs `CHROMIUM_PATH`.
- Local Docker CLI is still not installed. The hosted Docker build and synthetic `POST /api/analyze` smoke check now pass in GitHub Actions; this is not a real-dog validation.

The standalone timing script now has a unit-tested schema guard: AP-10K gait formulas are skipped unless the result schema is `ap10k`. Its peak-RSS probe is optional on platforms without Python's POSIX `resource` module. This does not constitute a new performance benchmark.

The static copy review was completed on October 22, 2026 for the pose-output labels, report titles, and safety/disclaimer wording. These labels now describe observational movement information rather than validated clinical measurements. The hosted smoke fixture was synthetic; it does not close the real-dog validation or live language-model provider checks. Abhi's live provider walk-through stays open.

## Browser checks (October 18, 2026)

Chrome opened `http://127.0.0.1:4173/` (the Vite dev server for the web app). No phone, no TensorFlow, and no walking clip from the repo. A 3-second generated MP4 was used only for the upload control. Saved results below were written into this browser's local storage as fixtures, not measured from a clip.

1. **Dark mode — passed for the labels that were checked, with a limit.** The web app has no theme control, and it does not follow the system preference. The active palette on a normal load is the light one: the title was `rgb(34, 61, 63)` and muted labels were `rgb(98, 125, 127)`. Adding the stylesheet's `dark` class on the page (the only hook the CSS has) changed the title to `rgb(245, 242, 234)`, muted labels to `rgb(161, 180, 181)`, and the companion card to the dark card color. The pet name uses the accent token, which is the same peach in both palettes. Before this pass, that name and the companion-card labels were hardcoded light colors and did not change. A missing score on the home trail, the history list, the trend table, and the overall indicator reads **Not scored**. Factor rows read **Not scored**. Unset measurements read **Not measured**. None of those was `0`.

2. **Demo mode — not run, not passed.** The web app has no demo screen and no "Sample data — not your pet" label. Overview, Analyze, History, AI use, and Pet profile were opened. None of them contained that sentence or the word demo. History and trends showed only the fixture walk. There is no vet-summary control on the web app, so that part was not opened.

3. **Server down — passed as observed.** The API was not running. Choosing `walk.mp4` and clicking Run analysis showed "The analysis service could not finish this clip. Please try again in a moment." The file name stayed `walk.mp4`, the preview stayed, and clicking Run analysis again showed the same message with the same file. There is no button labeled Retry. Vite answered the dead proxy with HTTP 500, so the message is the service-failure sentence, not a network-offline sentence.

4. **AI lines — passed.** The fixture listed `pose-model`, `motion-fallback`, `scoring`, `observation-rules`, and `development`. The result screen showed only the four registry sentences for the clip steps. The development sentence was not on that screen.

5. **Low confidence — passed with a fixture.** The banner heading was "Low confidence — try a clearer clip". Stride symmetry, asymmetry, hip stability, and pose confidence read "Not measured". Confident frames read "0 of 40" because the fixture stored zero frames past the gate. That is a count, not an unset limb.

6. **Concerning change and diagnosis — passed.** The same fixture showed "Worth asking a veterinarian about" and said the change is not a diagnosis. Every page that was opened uses "does not diagnose" or "not diagnosing". No screen claimed a diagnosis.
