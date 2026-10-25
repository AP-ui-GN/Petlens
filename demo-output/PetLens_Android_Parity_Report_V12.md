# PetLens Android Parity Report (Version 12)

Statuses: PASS / FAIL / PARTIAL / BLOCKED / NOT TESTED. Only what was observed on the emulator is marked PASS.

Test device: Android emulator `PetLens_Pixel` (Pixel 8, API 36, 1080x2400, 420 dpi, default font scale, dark theme).
Package `com.silverpaws.app`, versionName 0.1.0, versionCode 12 (installed and confirmed with `dumpsys package`).

## 1. Missing screens / states

| Screen or state | Status | Evidence |
|---|---|---|
| Overview (empty, then with saved walk) | PASS | `emulator/v11-overview.png`, `emulator/v12-overview.png` |
| Analyze: connection status, consent, stepper, upload card | PASS | `emulator/v11-analyze*.png` |
| Consent notes (3 steps + acknowledge) | PASS (see issue 2) | UI dump walkthrough |
| Android video picker, clip selection (30s, 1.3 MB) | PASS | `emulator/v11-picker.png`, `v11-selected.png` |
| Progress state ("Measuring movement", elapsed time, Cancel) | PASS | `emulator/v11-run-2.png`, `v11-run-8.png` |
| Result summary + "No usable signal" state | PASS | `emulator/v11-result.png` |
| Walk details + motion chart | PASS | `emulator/v11-detail.png`, `v11-detail2.png` |
| Pet profile list, edit form, save | PASS | UI dump, `emulator/v11-edit.png` |
| History tab | PARTIAL | Empty state seen in v10/v11; populated list not re-captured |
| Guided tour, compare, methodology, onboarding | NOT TESTED | Not opened on device in this pass |
| Delete/remove dialogs | NOT TESTED | |
| Offline error + Retry | PARTIAL | Offline banner seen once (transient); Retry then "Connected". Failed-upload retry not exercised |

## 2. Edit button root cause

- Cause: the 170px decorative `◒` ornament behind the pet card is positioned at the top-right, the same place as the mobile-only edit icon (the web card has the ornament but no button). The bare 21px icon sat on top of it, so a large partial circle read as part of the button.
- Fix (`mobile/app/(tabs)/index.tsx`): the edit control is now an opaque 40px bordered circle, and the ornament is moved lower so it sits beside the stats row instead of behind the button. The ornament position differs slightly from the web card on purpose.
- Verified on device in Version 12 (`emulator/v12-overview.png`): the button renders as a clean circle, and it opens the profile editor.
- Edit and save: age changed 6 to 7, Save, and Overview shows "Dog · 7 years". PASS.

## 3. Upload test (real device, real API)

| Stage | Status |
|---|---|
| File selection through Android picker | PASS |
| Upload and API request to `https://petlens-motion-api.onrender.com` | PASS |
| Server processing (about 50 s) | PASS |
| Response parsing | PASS |
| Results and chart rendering | PASS |
| Saved to history | PASS |

Caveat: the only clip available was a 30 s screen recording of the demo, not a dog walking. The server correctly returned "No usable signal". This proves the pipeline end to end. It does NOT validate analysis of a real dog walk, and no claim is made about gait findings. A real side-view dog clip is still needed.

## 4. API test

- `GET /api/healthz` returned `{"status":"ok"}`. The app's check showed "Connected".
- The first check on the freshly installed app failed with the "Offline" message and passed on re-entry. Cause not proven (probably transient network or cold start at launch).
- Production URL comes from `EXPO_PUBLIC_API_URL` in `mobile/eas.json`; no saved override was set (Advanced API address off).

## 5. Visual comparison

NOT DONE as a measured comparison. No web screenshots were captured at matching sizes, so no similarity figure is given. The Android screenshots in `demo-output/emulator/` follow the web layout and palette by inspection only.

## 6. Build and tests

- Mobile `pnpm run typecheck`: pass.
- `expo-doctor`, `export:check`, workspace typecheck, web tests and web build: NOT re-run in this pass (they passed on the pushed commit `f6f1b9b`).
- Build 12: EAS `6943ce84-0a69-47b9-9544-fd55c791b213`, FINISHED.

## 7. Original APK preservation

All earlier files are untouched; new files use new names. SHA-256:

| File | Bytes | SHA-256 |
|---|---|---|
| Version 6 | 114410721 | 376982B6444A15294C9C15D4CF90EAE4383791FD57F2F4DA30FAE4853161A7DF |
| Version 7 | 114404725 | A9276B0218D164CE260C2F0BD66FB710C50752C67058AD6DE3F9E6ED2AC3DDEA |
| Version 8 | 114406149 | 1222F416C2E2CCAEB71F327B83AD9F444B9D5A654B8F1FB975CB4FFD948DD1BC |
| Version 9 | 114406941 | B768D4D04503ECDF0F9CFC5CA4BE88BAF9D37C37E5D8E88BC83622DE355F6775 |
| Version 10 | 114406945 | C98319AC20D6A296DD1CF831E81F2170FA382FB3B8C86A8050A420730551E9AC |
| Version 11 | 114407049 | 25AA4D44392279028B20935AF92678C39229E0A3AC5932D08F24D3E76C86F410 |
| **Version 12** | 114407049 | 1AB5CF70AA3C410FC9F4E6423C9761BC9C9D3ADCA51A72FFF89850A5C0333B7E |

The web app (`artifacts/`) is unmodified (`git diff -- artifacts` is empty). APKs stay untracked (over GitHub's 100 MB limit).

## 8. Remaining issues

1. The offline message text ("Check the phone and laptop share a Wi-Fi network...") is a development hint and is wrong for a production build.
2. Opening the consent screen navigates away from Analyze and the selected clip is lost; the user must pick the clip again after accepting. Web behaviour not compared.
3. Overview shows "A steady picture" as the note title even when the latest result is "No usable signal". The web home page uses the same title, so this matches the web, but it is misleading.
4. A "No usable signal" result is saved to history; web behaviour not compared.
5. Not tested: guided tour, compare, methodology, onboarding, delete dialogs, a populated History list, real dog-walk analysis, failed-upload retry, side-by-side visual diff.
