# PetLens Android Parity Report — V13

Status key: PASS, FAIL, BLOCKED, NOT TESTED. Nothing below is claimed without evidence from this session.

## A. Summary
V13 fixes four reported bugs, adds a clip-readability check, passes every automated suite, and installs and runs on an Android emulator against the real production API. Dog-walk and clinical validation are **BLOCKED / NOT VALIDATED**: the only clip available is a 30 s screen recording (`20.mp4`), so the API correctly returned "No usable signal".

## B. Bug fixes
| # | Fix | Result |
|---|-----|--------|
| A | Offline messaging: failure kinds (offline / server unavailable / not configured), bounded auto-retry (1,2,4,8,16 s), single in-flight check, stale-update guard, manual Retry | PASS in unit tests (`connection-messages.test.ts`); on device an "Offline" first check recovered to "Connected" by auto-retry and "Unable to connect" showed on a failed upload in airplane mode. The manual Retry tap was NOT exercised. |
| B | Health-check lifecycle | PASS in code and tests. The original first-launch failure was **not reproduced**, so its root cause is unproven. |
| C | Selected clip survives the consent screen (`pending-selection.ts`, `router.back()`) | PASS on device: `20.mp4` still selected after consent |
| D | Honest headline: "No usable signal this time" for `unusable` signal quality (`headline.ts`, mobile + web) | PASS on device (upgrade over V12 data) and in the web browser; 20/20 web tests |
| + | `isClipReadable` before upload, duplicate-submission guard | Readable path PASS on device; unreadable-file path NOT TESTED on device |

Observation: after an airplane-mode failure, tapping "Try again" repeatedly while the network was already back showed the same error text in my UI dumps. I could not determine whether the taps started a new upload. Re-picking the clip and tapping Analyze worked end to end. Treat "Try again after a network failure" as **NOT PROVEN**.

## C. Screen audit
| Screen | Android (emulator) | Web fixture | Result |
|---|---|---|---|
| Overview | yes | yes (seeded) | PASS (visual differences below) |
| Analyze: empty / clip selected / consent / progress / result | yes | yes (empty) | PASS |
| Failed upload (airplane mode) | yes | n/a | PASS |
| History (1 walk), Compare disabled | yes | yes | PASS |
| History detail | yes | yes | PASS |
| Pet profile and create flow | yes | yes | PASS |
| Compare with 2 walks | – | – | NOT TESTED |
| Methodology, guided tour, delete confirm, profile edit/cancel, restart persistence | – | – | NOT TESTED |

Web screenshots use a browser-only seeded fixture (pet "Mabel", one "unusable" opencv-motion walk) — not real user data.

Visual differences vs web (qualitative; no similarity score computed): Android uses system Roboto where the web uses a custom font; tab-bar icons differ; the web ornament is a larger circle behind the card; the Android edit-button circle is mobile-only; the web hero has a dog silhouette image.

Screenshots: `demo-output/parity-v13/` (`web-*.png`, `android-*.png`).

## D. Automated verification (all exit 0)
| Command | Result |
|---|---|
| mobile `test` | 9/9 |
| mobile `typecheck`, `doctor`, `export:check`, `verify:eas-update` | pass; doctor 21/21 |
| web `test` / `typecheck` / `build` | 20/20 / pass / OK |
| api-server `test` / `typecheck` / `build` | 59/59 / pass / pass |
| Python `unittest discover -s tests -t .` | 160 OK (1 skipped) |
| `scripts/check_setup.py` | OK; validated canine pose capability: no |

## E. APK evidence
- `demo-output/PetLens_Version_13.apk`, 114,410,745 bytes, SHA-256 `D2B25A09B5001E54AB947FDAB56891B8C6D2962A81E6F6EA782383702CBB58D6`
- `com.silverpaws.app`, versionCode 13, versionName 0.1.0, label "PetLens AI"; EAS build `2b6e84df-86b6-483b-8adc-14fafbd2cdd1`
- EAS metadata records commit `f6f1b9b` because the working tree was dirty at build time; the build contained the uncommitted fixes (confirmed on device).
- Bundle contains `https://petlens-motion-api.onrender.com`. Two incidental strings exist: a `localhost:8081/api/healthz` string and a `192.168.1.20:8080` input placeholder; neither is the configured API address.
- Upgrade install over V12: data persisted. Clean install after `pm clear`: first-run empty state shown.
- V12 APK SHA-256 unchanged (`1AB5CF70…333B7E`). APKs are not committed.

## F. API / scientific validation (kept separate)
- Production `GET /api/healthz` → 200 `{"status":"ok"}`.
- Real upload of `20.mp4` from the V13 app → result "No usable signal", pipeline "Picture motion only", overall score not available, guidance to film a steady side-on clip. This proves the request/response path, not walking-analysis accuracy.
- Dog-walk validation: **BLOCKED** (no real dog-walk clip). Canine pose accuracy: not claimed.

## G. Repository changes
Mobile: `connection-messages.ts`, `pending-selection.ts`, `headline.ts`, `api.ts`, `use-connection.ts`, `connection-status.tsx`, `analyze.tsx`, `onboarding.tsx`, `index.tsx`, `settings.tsx`, `_layout.tsx`, tests and test script. Web (intentional exception): `headline.ts`, `home.tsx`, `tests/headline.test.ts`, test script.

## H. Blockers and limitations
No dog-walk clip; original first-launch failure unproven; manual Retry, post-failure "Try again", two-walk Compare, Methodology, tour, delete, profile editor and restart persistence not exercised on device; font/icon differences remain.

## I. Post-release verification — 2026-10-25

This follow-up preserves the V13 APK and adds evidence from the installed V13 app. The V13 SHA-256 still matches the value above. The test clip remained the same 30-second screen recording; results below verify application flows only, not dog-walk analysis.

### Retry after upload failure

**PASS — real-device retry flow:** On the Android emulator, selected `20.mp4`, enabled airplane mode, and tapped Analyze. The app showed the network-specific error and left the clip selected. After restoring connectivity, tapped the visible **Try again** control without reopening the picker. The screen showed upload progress ("Uploading clip · 35%") and then displayed the actual result with "No usable signal", "Picture motion only", and no overall score. History showed two saved observations (one existed before the retry); the failed attempt did not add a success-shaped entry. The retried clip was the still-selected `20.mp4`; it was not reselected or substituted.

Evidence: `parity-v13/r2-clip-selected.png`, `r2-t4.png` (failed network state), `r2-retry-t2b.png` (new upload in progress), `r2-retry-result.png` (real response), `v13-history-3.png` (saved records). The app does not expose a request ID in its UI, so the second HTTP request was not independently traced in logs; the new upload progress followed by the API result is direct UI evidence of the second submission.

### Regression coverage and implementation

**PASS:** Extracted the async readability/URL/request/result handling into `mobile/src/lib/analysis-attempt.ts`, used directly by Analyze. Each press rechecks the same selected URI, and only a successful result reaches record creation. A synchronous submission gate rejects duplicate rapid taps before React state updates. Added deterministic tests for failed attempt then same-clip retry, a second failure, successful response, unreadable file, missing URL, upload progress, and concurrent taps.

`node --experimental-strip-types --test --test-concurrency=1 tests/*.test.ts`: **16/16 passed**. Mobile typecheck passed. The existing V13 device run also demonstrated upload failure and subsequent successful retry; no app-level retry is automatic after a user explicitly cancels.

### Health-check recovery

**PASS:** Started V13 in airplane mode; the app showed **Offline**. Restored connectivity and tapped the inline **Retry** control; it changed to **Connected** and "The analysis server answered." This verifies manual health retry and recovery. Bounded retry / one in-flight check behavior remains covered by code and prior tests. The original intermittent first-launch failure was not reproduced; its root cause remains unknown.

Evidence: `parity-v13/hc-1-offline.png`, `hc-2-network-back.png`, `hc-3-after-retry.png`.

### Screen checks

| Screen / behavior | Device result |
|---|---|
| Profile editor: cancel unsaved breed change | **PASS** — reopening retained "Labrador mix" |
| Profile editor: save breed change | **PASS** — saved "Retriever" and profile card reflected it |
| Restart persistence | **PASS** — after force-stop/relaunch, "Retriever" and saved observations remained |
| Compare / insufficient data | **PASS, limited** — selected two saved same-method (`Picture motion only`) records; dates and actual saved metrics displayed as "Not measured". Both were generated from `20.mp4` screen-recording runs, not dog walks. With one record, Compare was disabled. A cross-method/incompatible pair was **NOT TESTED**. |
| Methodology | **PASS** — opened, scrolled to the sources/disclaimer, and verified it says default analysis measures whole-picture frame motion and explicitly disclaims validated canine keypoints and clinical claims. Added a Stack screen entry for a titled native header; confirmed the "Methodology" header on V15. |
| Guided tour | **PASS** — opened; Next and Back changed steps; Skip dismissed it; a separate run advanced to step 4 and Finish dismissed it; tab navigation remained available. |
| Delete confirmation | **PASS** — Keep left the two observations intact; confirming Delete removed only the selected walk and left one observation. |
| Vet summary export | **PASS** — invoking it opened Android's share sheet with a generated PDF. |
| Unreadable/revoked URI | **NOT TESTED** on device. |

Evidence: `parity-v13/v13-edit-form.png`, `v13-edit-typed.png`, `v13-pet.png`, `v13-restart-overview.png`, `v13-compare.png`, `v13-methodology.png`, `v13-tour-1.png`, `v13-tour-last.png`, `v13-delete-dialog.png`, `v13-before-delete.png`, `v13-after-delete.png`, `v13-vet-summary.png`.

### Release state

- V13 remains unchanged: `PetLens_Version_13.apk`, versionCode 13, SHA-256 `D2B25A09B5001E54AB947FDAB56891B8C6D2962A81E6F6EA782383702CBB58D6`.
- **Patch build PASS:** EAS build `a3ebd486-a2a5-4787-9b11-7399c222ac28` finished 2026-10-25 3:09 PM. Remote auto-increment assigned versionCode **15**; no V14 APK was created or substituted for V13.
- Separate APK: `demo-output/PetLens_Version_15.apk`, 114,413,861 bytes, SHA-256 `66327AB5663BCAC6312AAB6FD66A576118968651435DA97ED5026BCAE114C13A`; package `com.silverpaws.app`, versionName `0.1.0`, versionCode 15, label `PetLens AI`.
- Installed over V13 on the emulator: **PASS**. Existing pet and one saved analysis persisted. Overview showed "No usable signal this time"; the detail screen opened; Methodology displayed the corrected native title and scrolled to its sources and non-diagnostic disclaimer. Screenshots: `parity-v13/v15-launch.png`, `v15-history.png`, `v15-detail-bottom.png`, `v15-methodology-top.png`, `v15-methodology-bottom.png`.
- APK bundle contains `https://petlens-motion-api.onrender.com`; `localhost:8081` occurs only as a development health-check string. The EAS metadata commit is parent `4e4d1ef`; the EAS upload was made from the working tree with the patch changes present but not yet committed.
- Exact commands from `mobile/`: `node --experimental-strip-types --test --test-concurrency=1 tests/*.test.ts` (**16/16 PASS**); `pnpm run typecheck` (**PASS**); `pnpm run doctor` (**21/21 PASS**); `pnpm run export:check` (**PASS**); `pnpm run verify:eas-update` (**PASS**).
- GitHub publication: commit `4ec6422502a33802506dd85287cb3e9658c6fe33` pushed to `main` as a fast-forward; the verified `origin/main` SHA matched that commit. APKs and local environment files were not committed.
- Existing web/API/Python source was unchanged in this follow-up; those suites were not rerun.
- **BLOCKED / NOT VALIDATED:** dog-walk analysis, canine-pose accuracy, osteoarthritis detection, and clinical reliability. No suitable dog-walking clip was available.
