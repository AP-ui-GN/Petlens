# Expo testing

Shared testers should use an EAS **preview** build. Expo Go is for local
development and does not verify standalone APK behavior or EAS Update delivery.
See [`MOBILE_RELEASE.md`](MOBILE_RELEASE.md) for the build and OTA release
commands.

## Build a preview APK

From `mobile/`, sign in to the EAS account that owns the existing project,
then validate and build:

```sh
npx eas-cli@latest whoami
npm run verify:eas-update
npx expo install --check
npm run typecheck
npx eas-cli@latest build --platform android --profile preview
```

Share the install link shown on the successful EAS build page. Preview builds
listen only to the `preview` update channel; do not send a preview update to
production.

## Test the app

On an installed preview build:

1. Open Settings → App updates and confirm the version, runtime, preview
   channel, and current bundle are shown truthfully.
2. Confirm the production API connection, choose a short side-on walking clip,
   and inspect the saved result. Do not treat synthetic media or sample results
   as evidence of dog analysis.
3. Create a pet and review History; sample data must not appear as a real saved
   walk. Compare only results from the same analysis pipeline.
4. Repeat launch and core navigation while offline. The embedded/cached app
   should remain usable even though analysis requires a reachable API.
5. For OTA testing, publish a harmless, intended test change to the preview
   channel, launch the app online to download it, fully close and reopen the
   app, then verify the changed behavior and OTA bundle status. Do not use the
   production channel for a test update.

The app does not diagnose medical conditions. The production API currently
provides OpenCV motion measurements only; pose and gait measurements are not
available on that service.

In Settings, **Send feedback** opens the share sheet with the app version and
device details; it does not attach a video.
