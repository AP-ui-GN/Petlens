# Android APK build

The Expo production profile is configured to create an installable Android APK.
It uses EAS remote versioning and the `production` EAS environment.

## Required before building

1. The production profile in `mobile/eas.json` supplies
   `EXPO_PUBLIC_API_URL=https://petlens-motion-api.onrender.com`. This is a
   public URL, not a secret; it is embedded in the app bundle. The no-cost
   Render service runs motion-only analysis and can sleep while idle. Do not
   replace it with `localhost` or a private LAN address.
2. Before release, confirm the deployed server's `/api/healthz` and
   `/api/analyze` endpoints are reachable from a phone using that URL.
3. Sign in to the EAS project and use the EAS CLI version required by
   `mobile/eas.json`.

## Build

From the `mobile` directory, run:

```sh
eas build --platform android --profile production
```

The build page provides the APK when the build succeeds. The app's package
identifier is currently `com.silverpaws.app`; replace it with a team-owned
identifier before public store distribution.

## Local verification

Run `pnpm typecheck` in `mobile` before submitting changes. A successful
TypeScript check is not an APK build or a device-install test. The production
API is motion-only; it does not provide canine pose or gait measurements. A
release build without a reachable server displays an explicit connection
error rather than guessing a laptop address.
