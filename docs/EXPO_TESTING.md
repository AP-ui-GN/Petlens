# Expo testing

Shared testers should install a **preview** build. **Expo Go** is only for
development against a dev server on your laptop (`npm start` in `mobile/`).

This guide was checked against the Expo docs for EAS Build, internal
distribution, and EAS Update (docs.expo.dev, October 2026). It does not run a
build. Nobody is signed in to Expo, Apple, or Google from this repository.
There is no install link and no build URL yet.

The bundle id and Android package are the placeholder `com.silverpaws.app`.
Replace them before a store release. The previous ids in this repo were
`org.silverpaws.mobile`.

The icon, adaptive icon, and splash in `mobile/assets/` are Expo template
placeholders. `attached_assets/` has no artwork. Replace them before testers
see a branded app.

## Before the first preview build

From `mobile/`, with Node and npm:

```bash
npm install --global eas-cli
eas login
eas whoami
```

`eas login` is the sign-in step. `eas whoami` prints the account that will own
the project. You can use `npx eas-cli@latest` instead of a global install.
Use that form in place of `eas` in the commands below if you do.

Set `EXPO_PUBLIC_API_URL` to the HTTPS API address from `docs/HOSTING.md`.
In the Expo project, put it on the **preview** and **production** EAS
environments. Do not put server secrets in any `EXPO_PUBLIC_` name. The only
public value is the API address.

Then, still in `mobile/`:

```bash
eas update:configure
```

That command writes `runtimeVersion`, `updates.url`, and `extra.eas.projectId`
after you are logged in. This repo sets `runtimeVersion` policy `appVersion`
in `mobile/app.config.ts` and does not invent a project id or an updates URL.
Run `eas update:configure` before the first preview build so the binary can
receive JavaScript updates. It also installs the updates client if it is missing.

`mobile/eas.json` already gives each profile its own channel:

| Profile | Channel | Who it is for |
| --- | --- | --- |
| `development` | `development` | A dev client, not for shared testers |
| `preview` | `preview` | Testers. Internal distribution |
| `production` | `production` | A later store build |

## Build the preview profile

Android, from `mobile/`:

```bash
eas build --platform android --profile preview
```

Internal distribution produces an APK. When the build finishes, the Expo
website shows an install URL. Send that URL to Android testers. Do not paste a
made-up link into this repo.

iOS, from `mobile/`:

```bash
eas device:create
eas build --platform ios --profile preview
```

`eas device:create` registers a device and gives you a URL or QR code for the
tester to register. An ad hoc preview build installs only on devices that were
registered before that build. Share the install URL from the finished build
page with those people.

TestFlight is separate. It needs an App Store Connect app and
`eas submit --platform ios`. Use it when you want a wider iOS tester list than
ad hoc allows. This repo does not submit anything.

## JavaScript-only fixes

Native changes (new permissions, a new Expo package with native code, the
bundle id) need a new `eas build`. JavaScript and asset fixes can go to testers
who already installed the preview build:

```bash
eas update --channel preview --message "What changed" --environment preview
```

`--environment` is required for SDK 55 and later. This app is on SDK 57.
The preview binary listens to the `preview` channel. Do not publish a tester
fix to `production`.

Testers load the update by force-closing the app and opening it again, up to
two times. Development builds can also load an update from the Extensions tab.

## What to test

On a saved result, the AI-use lines should name only the steps that produced
that walk: experimental COCO-17 output only when explicitly enabled, frame
motion (which runs on every clip), fixed scores and a fixed note, and a
language-model reword only when the server kept one. COCO-17 output is not
validated canine pose and is disabled by default.

Also walk through: create a pet, record or choose a short side-on clip, confirm
the server connection chip, open the saved walk, and try Compare only with two
walks from the same pipeline. Demo mode's sample must not appear in History.

## Feedback

In the preview app, Settings → **Send feedback** opens the share sheet with the
app version and the device. It does not attach a video. Testers can also reply
on the install page if you gave them one.

The development note in `docs/AI_USE.md` stays: parts of this app's code and
documentation were written with AI coding assistants and reviewed by the team.
That is not a step that runs on a clip.
