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
