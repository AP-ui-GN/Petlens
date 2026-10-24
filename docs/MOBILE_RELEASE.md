# Android APK build

The Expo production profile is configured to create an installable Android APK.
It uses EAS remote versioning and the `production` EAS environment.

## Required before building

1. Set `EXPO_PUBLIC_API_URL` in the EAS `production` environment to the
   deployed API's public HTTPS base URL, for example
   `https://api.example.org`. Do not use `localhost` or a private LAN address:
   those point at the device itself or are unreachable outside that network.
   The value is embedded in the public app bundle and must not contain secrets.
2. Confirm that the deployed server's `/api/healthz` and `/api/analyze`
   endpoints are reachable from a phone using that URL.
3. Sign in to the EAS project and install/use the EAS CLI version required by
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
TypeScript check is not an APK build or a device-install test. The repository
does not include a production API address, and a release build without the
production `EXPO_PUBLIC_API_URL` displays an explicit missing-server message
instead of guessing a laptop address.
