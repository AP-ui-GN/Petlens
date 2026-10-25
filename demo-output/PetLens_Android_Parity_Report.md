# PetLens Android parity report

## Reference and changes

The Vite web app was inspected in its mobile layout at `/`, `/pet`, and `/analyze`. The browser viewport was 628 x 828 CSS pixels at 1.25 device scale; the web interface uses Plus Jakarta Sans. Native changes align the shared palette, panel and button geometry, branded header, inset tab bar, overview hierarchy, and analysis upload steps with that reference. Camera and gallery selection, consent, sample mode, analysis requests, progress, and saved results remain native.

Short comments explain the picker defaults, safe-area spacing, the flattened native panel colors, and clamping legacy scores in the overview bar. Analysis-only UI now lives under `mobile/src/components/analysis/`, separate from the route's upload and API state.

## Checks

- Mobile TypeScript: passed.
- Expo Doctor: 21/21 checks passed.
- Android Metro export: passed.
- Workspace typecheck: passed.
- Web production build: passed (with an existing source-map warning in `tooltip.tsx`).
- Web unit tests: 19 passed.
- `git diff --check`: passed.
- APK ZIP integrity check: passed.

## APK

- File: `PetLens_Version_8.apk` in this directory.
- EAS build: `bd67c413-4057-46ba-8e63-3b81a902df57` (production, finished).
- Package: `com.silverpaws.app`; version: `0.1.0` (versionCode 8).
- Size: 114,406,149 bytes.
- SHA-256: `1222F416C2E2CCAEB71F327B83AD9F444B9D5A654B8F1FB975CB4FFD948DD1BC`.
- APK archive integrity: passed; Android manifest and DEX files are present.

## Visual verification limits

The web reference was visually inspected, but no Android device or emulator is available (`adb` and Android SDK environment variables are absent). Therefore the APK was not installed, launched, or captured; there is no Android screenshot, before/after overlay, or defensible pixel-similarity score.

Known remaining differences include the native system font instead of bundled Plus Jakarta Sans, solid native card surfaces instead of the web gradients, and no inline native video preview after selection. The native APK build and bundle are verified, but visual parity and on-device workflow behavior remain unverified.
