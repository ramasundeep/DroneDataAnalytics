# CD Sim — Instructor Console

React + TypeScript web UI for CD Sim instructors (ADR 0009). This is the
**Phase 0 skeleton**: it shows the health of the platform services and lists
the platforms, areas and scenarios the API knows about. Every other
instructor workflow is a clearly marked placeholder.

CDPL proprietary. Every screen carries the Chakravyuha Dynamics logo
placeholder (`src/assets/cdpl-logo-placeholder.svg`) — swap in the official
asset when it is supplied.

## What is in Phase 0

| Route        | Data source                 | Notes                                                           |
| ------------ | --------------------------- | --------------------------------------------------------------- |
| `/`          | `GET /api/v1/system/health` | Card per service, status pill, latency, detail; polls every 5 s |
| `/platforms` | `GET /api/v1/platforms`     | Table                                                           |
| `/areas`     | `GET /api/v1/areas`         | Table (bounds, landing pads, classification)                    |
| `/scenarios` | `GET /api/v1/scenarios`     | Table                                                           |

## What is not (yet)

These nav items render a "Planned — Phase N (see `docs/10_ROADMAP.md`)" page
and show no data — real or sample:

| Item         | Phase |
| ------------ | ----- |
| Sessions     | 4     |
| Live monitor | 4     |
| Replay       | 3/4   |
| Trainees     | 4     |
| Fleet        | 5     |
| Maintainer   | 6     |

There is no authentication in Phase 0.

## How it talks to the API

All requests use the relative base path `/api` (`src/api/client.ts`,
types in `src/api/types.ts`). The `/api` prefix is stripped before the
request reaches the API service:

- **Dev** — the Vite dev server proxies `/api/*` → `http://localhost:8000/*`
  (override with `CDSIM_API_URL`).
- **Production** — the bundled nginx proxies `location /api/` →
  `http://api:8000/` (the compose service name).

If the API is down the status page shows an error banner and keeps retrying;
table pages show an error message.

## Commands

Requires Node.js 20+. Dependency versions are pinned exactly and locked in
`package-lock.json` so offline/cached builds are reproducible. Use `npm ci`
for installs. When regenerating the lockfile, use npm 11+
(`npx npm@11 install`): npm 10.9 crashes while resolving vitest's optional
peer dependencies (`Cannot read properties of null (reading 'edgesOut')`).
`npm ci` on the committed lockfile works with npm 10.

```bash
npm ci                 # install (use `make setup` from the repo root)
npm run dev            # dev server on http://localhost:5173
npm run build          # type-check (tsc -b) + production build to dist/
npm run preview        # serve dist/ locally
npm test               # vitest (jsdom)
npm run lint           # eslint
npm run format         # prettier --write
npm run format:check   # prettier --check
npm run typecheck      # tsc --noEmit
```

The root `Makefile` calls `npm test`, `npm run lint`, `npm run format:check`
and `npm run typecheck`.

## Environment

| Variable        | Used by        | Default                 |
| --------------- | -------------- | ----------------------- |
| `CDSIM_API_URL` | Vite dev proxy | `http://localhost:8000` |

The production image has no runtime configuration; the API is always reached
at `http://api:8000` on the compose network.

## Docker

```bash
docker build -t cdsim/instructor-console apps/instructor-console
```

Multi-stage: `node:20-alpine` runs `npm ci && npm run build`, then
`nginx:1.27-alpine` serves `dist/` with an SPA fallback. `GET /healthz`
returns `200 ok` for the compose health check. The runtime image needs no
internet access and loads no external fonts or CDNs.
