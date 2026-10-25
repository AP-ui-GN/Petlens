# Mobile APK and EAS Update releases

PetLens uses Expo SDK 57 and the existing EAS project
`f2e7a1b9-741f-4395-89cd-aafcfef0433d`. The production Android profile builds
an APK on the `production` channel; preview and development builds use separate
channels. `expo-updates` is configured to check on launch without waiting for
the network before opening the app.

## What can ship over the air

EAS Update can deliver JavaScript and bundled asset changes that are compatible
with the installed native runtime. PetLens uses Expo's `fingerprint` runtime
policy: EAS computes a runtime version from native compatibility inputs, so
only builds with a matching fingerprint receive an update. Keep native
dependencies and configuration unchanged for OTA-only releases. Changes to
Expo/React Native or native dependencies, permissions, native modules, Android
configuration, or anything else that changes the native runtime require a new
APK. Do not promise OTA delivery for native changes.

On launch, the app immediately opens its embedded or cached bundle. An
automatic update check runs in the background; when a compatible update is
downloaded, it becomes active after the app is fully closed and opened again.
If the network or update service is unavailable, the cached/embedded bundle
remains available. Expo Updates recovery can fall back from an update that
fails during startup. Settings → App updates shows the app/runtime versions,
channel, and whether the running bundle is embedded or an update.

## One-time setup and checks

From `mobile/`, use the project account that owns the configured EAS project:

```sh
npx eas-cli@latest login
npx eas-cli@latest whoami
npm run verify:eas-update
npx expo install --check
npm run typecheck
npx expo-doctor
```

The configuration check validates the project ID and URL, update launch
behavior, fingerprint runtime policy, APK output, production API URL, and
separate development/preview/production channels. `expo-updates` is already
installed at the version paired with this Expo SDK. Do not run
`eas update:configure` to replace the existing project configuration.

The Android package identifier is `com.silverpaws.app`; confirm the team owns
it before public distribution. The production API URL is a public endpoint,
not a secret, and is embedded in the app. Never put server credentials in
`EXPO_PUBLIC_` variables.

## OTA-only release

Use this only for tested JavaScript or asset changes. First publish to preview
and verify it on a preview installation; publish to production only for an
intended production release. Keep the native dependency set and configuration
unchanged for an OTA-only release.

```sh
npm run verify:eas-update
npx expo install --check
npm run typecheck
npm run update:preview -- --message "Describe the tested change"
```

After checking the published update in EAS and on a preview-installed device,
publish the intended release:

```sh
npm run update:production -- --message "Describe the production change"
```

The EAS CLI prints the update group and branch/channel. Verify that result in
the EAS dashboard before calling the update published. To verify receipt,
launch a production APK on a device after publication, wait for the
background download, fully close and reopen the app, and confirm Settings →
App updates reports an OTA bundle. Do not claim end-to-end delivery from a
successful publish or configuration check alone.

## Native Android release

Native changes require a new production APK; an OTA update cannot change the
native runtime. Bump the app version as appropriate for the release, then run:

```sh
npm run verify:eas-update
npx expo install --check
npm run typecheck
npx expo-doctor
npm run build:android:production
```

The production profile uses EAS remote versioning, increments Android
`versionCode`, keeps the production API URL, and produces an APK. Confirm the
EAS build is successful and download the artifact from that exact build.
Install and test it on an Android device or emulator when available. Publish a
compatible OTA only after that release is intended and tested.

## Scope and verification

OTA support does not change PetLens's analysis capability. The production
service currently reports `opencv-motion` only; pose and gait values remain
unavailable unless the backend is separately upgraded and validated.
Configuration validation, EAS publication, and installed-device receipt are
three different levels of evidence. Record which level was actually verified
for each release. Do not publish an experimental or known-broken change to the
production channel.
