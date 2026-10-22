# PetLens AI — mobile app (Expo Go)

The phone version of PetLens. Same pet profiles, same walk analysis, same
history view as the web beta, running in **Expo Go** so testers can try it
without an app-store build.

Every measurement still comes from the Python pipeline behind the API in
`artifacts/api-server`. The phone records or picks a clip, uploads it, and
shows the JSON that comes back. No scoring happens on the device.

## Try it in 5 minutes

You need: a laptop with the repo, a phone with **Expo Go** installed
([iOS](https://apps.apple.com/app/expo-go/id982107779) /
[Android](https://play.google.com/store/apps/details?id=host.exp.exponent)),
and both on the **same Wi-Fi network**.

**1. Start the analysis API on the laptop** (from the repo root, with the
Python `.venv` set up as described in the root `README.md`):

```bash
pnpm --filter @workspace/api-server run dev
```

It listens on port 8080 on every network interface. The first time, Windows
may ask to allow Node through the firewall — allow it on private networks.

**2. Start the mobile dev server:**

```bash
cd mobile
npm install
npm start
```

**3. Scan the QR code** with the Camera app (iOS) or Expo Go (Android).

The app works out how to reach the API by itself: Expo tells it which laptop
served the bundle, and the API is assumed to be on that laptop at port 8080.
If your setup differs, open **Settings → Analysis server**, type the address
(for example `192.168.1.20:8080`), and press **Test connection**.

If the phone cannot see the laptop at all (guest networks, some school Wi-Fi),
run `npm run start:tunnel` instead and set the API address by hand.

## What the app does

| Tab | What you can do |
| --- | --- |
| Home | See each pet with its latest overall score; add or edit pets |
| Analyze | Pick a pet, **Record** a walk with the camera or **Choose video**, watch upload progress, get the saved result |
| History | Every saved walk, filterable by pet, with a trend comparison |
| Walk details | Overall score, five factors with bars, **raw measurements** grid, observation text, limitations, share sheet, delete |
| Settings | API address + connection test, delete local data, full safety text |

Everything is stored on the phone with AsyncStorage. There are no accounts.

## Layout

```text
mobile/
  app/                      expo-router screens (file = route)
    _layout.tsx             providers + root stack
    (tabs)/                 Home, Analyze, History, Settings
    history/[id].tsx        one saved walk
    pet/[id].tsx            create ("new") or edit a pet
  src/
    lib/types.ts            mirrors lib/api-spec/openapi.yaml
    lib/api.ts              API address, clip checks, upload, error messages
    lib/storage.ts          AsyncStorage read/write, result → record
    lib/format.ts           labels and number formatting
    lib/disclaimers.ts      same text as the web app
    hooks/use-local-data.tsx  one in-memory copy of pets + walks
    components/             ui.tsx, score.tsx, trend-panel.tsx, disclaimer-footer.tsx
  metro.config.js           keeps Metro inside this folder (pnpm monorepo above)
```

The mobile app is a standalone **npm** project on purpose. Expo pins exact
React and React Native versions, and keeping it outside the pnpm workspace
means it can never fight the web app's dependency catalog.

## Checks

```bash
npm run typecheck        # tsc --noEmit
npm run doctor           # expo-doctor (21 checks)
npm run export:check     # full Metro bundle for iOS without a device
```

## Limits worth knowing

- A useful walk is about 5 to 15 seconds. The server accepts a longer clip, up to 120 seconds and 60 MB. A 10-second
  1080p phone clip is usually 15–30 MB; the picker asks for medium quality.
- Expo Go allows plain `http://` to the laptop. A store build would need
  HTTPS or an explicit cleartext exception.
- The trend view only compares walks that share a pipeline (`dog-pose`,
  `movenet`, or `opencv-motion`). A missing score is shown as “Not scored”,
  not as zero. New server results use `dog-pose`. `movenet` remains so an
  older saved walk can still be opened.
