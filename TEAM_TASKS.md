# TEAM TASKS

Sudarshan, Kavin, and the explanation-request part of Abhi's card were finished
on October 18, 2026. The markers in those files were removed. The static
observational copy review was completed on October 22, 2026. Abhi's live
provider walk-through remains open because no provider credentials are
configured. Optional follow-ups stay in `docs/PROJECT_STATUS.md`.

The markers in the listed files look like:

```
# ==================================================
# TEAM TASK: NAME
# PURPOSE: ...
# ==================================================
```

---

# ==================================================
# TEAM TASK: SUDARSHAN — done October 18, 2026
# PURPOSE:
# Finish the quality-of-life scoring model.
# ==================================================

STATUS: Done. `mobility_factor` and `historical_change_factor` return real
scores or `None`. `DEFAULT_WEIGHTS` includes both. `CONCERNING_DROP` (10) and
`CONCERNING_ASYMMETRY` (20) were reviewed and kept. Head-bob measurement was
not part of this pass.

TEAM MEMBER: Sudarshan
TASK: Score mobility and historical change, then calibrate the weights
FILE / MODULE: `gait_engine/wellness.py` (`mobility_factor`, `historical_change_factor`, `DEFAULT_WEIGHTS`)
WHAT TO IMPLEMENT:
- `mobility_factor(measurements)` — return a 0–100 score (or `None`) from pose measurements the pipeline already saves: `hipStability`, `leftAnkleMotion`, `rightAnkleMotion`, `strideSymmetry`.
- `historical_change_factor(overall, previous_overall)` — turn the change against the previous saved walk into a 0–100 factor, or `None` on a first walk. The pipeline already calls this after the overall score is computed (`gait_engine/pipeline.py`).
- Add `"mobility"` and `"historicalChange"` entries to `DEFAULT_WEIGHTS` once those functions return real scores. Until a weight exists, `overall_score()` ignores that factor.
- Review `CONCERNING_DROP` and `CONCERNING_ASYMMETRY`. Decide whether those thresholds still make sense.
- Keep `build_observation()` honest: it may only mention measured values.
WHY IT MATTERS:
- This is the analytical heart of the product. Owners should be able to see *why* a score moved.
DEPENDENCIES:
- Measurements already produced by `gait_engine/pipeline.py` and `gait_engine/features.py`
- Tests in `tests/test_wellness.py` (add cases for the new scores)
COMPLETION CRITERIA:
- Mobility and historical change are scored when the clip supports them, and left as `None` otherwise
- Weights are documented and easy to change
- `python -m unittest discover -s tests -t .` still passes
- Observation text never invents a number or a diagnosis

---

# ==================================================
# TEAM TASK: KAVIN — done October 18, 2026
# PURPOSE:
# Finish the trend view, form validation, and selected tests.
# ==================================================

STATUS: Done. The web trend panel compares saved walks and keeps
different pipelines apart. The pet form blocks a blank name and an
age or weight that is present but not a positive number. Automated checks:
`pnpm --filter @workspace/silverpaws-beta run test`.

TEAM MEMBER: Kavin
TASK: Historical trends, validation messages, and a testing checklist
FILE / MODULE:
- `artifacts/silverpaws-beta/src/components/trend-panel.tsx`
- `artifacts/silverpaws-beta/src/pages/pet.tsx`
- `TESTING.md`
WHAT TO IMPLEMENT:
1. **Trend panel** — replace the placeholder in `trend-panel.tsx` with a real comparison of saved walks. Show date, overall score, movement consistency, and symmetry. Only compare records that share the same pipeline. Handle empty, one-walk, and many-walk states. Do not invent chart data.
2. **Pet form validation** — in `pet.tsx`, show a visible message when name is blank, or when age/weight is present but not a positive number. Do not save until those checks pass.
3. **Testing** — add a short automated check (Playwright, Vitest, or a node test) for one of: pet save, clip-type rejection, or history empty state. Update the checklist in `TESTING.md`.
WHY IT MATTERS:
- Owners need to see direction over time, not a single number, and the form should explain itself when something is wrong.
DEPENDENCIES:
- Saved analysis fields in `src/lib/storage.ts` (`createdAt`, `overallScore`, `factors`, `pipeline`)
- History page already mounts `<TrendPanel analyses={analyses} />`
COMPLETION CRITERIA:
- Trend panel uses only saved records
- Invalid pet input shows a message the user can act on
- At least one automated UI/unit test is documented in `TESTING.md` and can be run locally

---

# ==================================================
# TEAM TASK: ABHI — request done October 18, 2026; live clip still open
# PURPOSE:
# Connect the optional language-model rewrite, then harden the live path.
# ==================================================

STATUS: `requestModelRewrite` is implemented and covered by mock-provider
tests. A live clip through UI → API → pipeline with the env vars set has not
been run, because this environment has no provider. Do not mark that line done
until someone records the result in `TESTING.md`.

TEAM MEMBER: Abhi
TASK: Provider request for the explanation rewrite, plus integration checks
FILE / MODULE: `artifacts/api-server/src/lib/explanation.ts` (`requestModelRewrite`)
WHAT TO IMPLEMENT:
- Send `buildExplanationPrompt(context)` to the configured chat-completions endpoint.
- Read `SILVERPAWS_LLM_URL`, `SILVERPAWS_LLM_KEY`, and `SILVERPAWS_LLM_MODEL`.
- Abort a slow request. Return `null` (never throw) on any provider error.
- Never log the API key.
- Leave `validateExplanation()` and the rule-based fallback alone — they already reject invented numbers, diagnoses, certainty language, and dropped vet recommendations.
- After the rewrite works, run a live clip through UI → API → pipeline and record the result in `TESTING.md`.
WHY IT MATTERS:
- A model may only *rephrase* measured findings. The product must stay usable when the provider is missing or returns junk.
DEPENDENCIES:
- Rule-based observation from `gait_engine/wellness.py`
- Validation tests in `artifacts/api-server/tests/explanation.test.ts`
COMPLETION CRITERIA:
- With no env vars set, the app still returns the rule-based observation (`usedLlm: false`)
- With a provider configured, a validated rewrite can replace that text (`usedLlm: true`)
- An invalid rewrite is discarded and the fallback is shown
- `pnpm --filter @workspace/api-server run test` still passes

---

# ==================================================
# TEAM TASK: PRODUCT / RESEARCH
# PURPOSE:
# Keep the wording observational.
# ==================================================

TEAM MEMBER: All three
STATUS: Static copy review completed October 22, 2026. Pose labels and report
headings describe observational movement information; the model output schema
and remaining limitations are stated explicitly. The live pose model was not
validated on labeled dog clips, and the live language-model provider remains
unconfigured.
TASK: Review user-facing copy and disclaimers
FILE / MODULE: `artifacts/silverpaws-beta/src/lib/disclaimers.ts`, observation text, report PDF
WHAT TO IMPLEMENT:
- Confirm the app never claims a diagnosis or emergency role
- Confirm a concerning change points to a veterinarian
WHY IT MATTERS:
- Trust depends on honest language.
DEPENDENCIES:
- Current copy in the footer, history detail, and PDF report
COMPLETION CRITERIA:
- A stranger reading the app can tell this is a wellness note, not a medical result
