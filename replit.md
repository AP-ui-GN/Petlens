# PetLens

PetLens is a local-first pet movement observation app that helps owners notice mobility patterns and compare changes over time without claiming medical diagnosis.

## Run & Operate

- `pnpm install` — install workspace dependencies and native platform binaries
- `pnpm build` — typecheck + build all workspace packages
- `pnpm --filter @workspace/api-server run dev` — run the backend development server
- `pnpm --filter @workspace/silverpaws-beta run dev` — run the frontend app in development mode
- `pnpm typecheck` — full TypeScript validation
- `PORT` and `BASE_PATH` are optional for local builds; both default to safe local values when missing

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- Frontend: Vite + React + Tailwind
- API: Express 5
- Analysis: gait-related metrics and observation logic in `gait_engine/`
- Storage: local browser storage for beta flow

## Where things live

- `artifacts/silverpaws-beta/` — user-facing product app
- `artifacts/api-server/` — backend route and runtime scaffolding
- `gait_engine/` — gait and movement analysis logic
- `lib/` — shared typed API and DB contracts
- `docs/` and root markdown files — project documentation

## Architecture decisions

- Keep human-facing app logic separate from AI/analysis code
- Save structured measurements and interpretation separately
- Use transparent, explainable caveats instead of medical certainty
- Prefer local-first storage in the beta phase so the app stays simple and reliable

## Product

The app allows pet owners to create a profile, upload a walking video, review the clip, and save a structured observation with raw measurements and plain-language interpretation.

## User preferences

- Keep the app observational and educational
- Do not imply medical diagnosis
- Preserve teammate task boundaries for future model and UI work
- Prefer transparent, understandable explanations over opaque scoring

## Gotchas

- Use pnpm rather than npm for workspace installs
- Install native optional platform dependencies before a clean build if the environment is missing them
- Vite config defaults allow local builds without required env values in the first pass
