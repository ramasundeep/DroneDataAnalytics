# Contributing to CD Sim

Read `CLAUDE.md` first — it holds the ground truth, fixed tech decisions and
conventions. This file covers the mechanics of getting a change merged.

## Branching

- `main` is always buildable and green. Nobody pushes to it directly.
- Branch from `main`: `<type>/<short-kebab-description>`, e.g.
  `feat/recorder-audio-ingest`, `fix/simclock-rate-jump`, `docs/sitl-ports`.
- Keep branches short-lived (days, not weeks). Rebase or merge `main` in
  often; prefer a merge commit over force-pushing a branch others use.
- One logical change per pull request. A PR that "also refactors X" should
  usually be two PRs.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <imperative summary, ≤ 72 chars>

<body: what and WHY, wrapped at 72. Mention anything not tested.>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`,
`chore`. Scopes are top-level areas: `sim`, `api`, `recorder`, `assessment`,
`sitl`, `rl`, `terrain`, `console`, `schemas`, `platforms`, `common`.

If a commit contains code that could not be built or run (e.g. UE5 C++ on a
machine without the engine), the body must say so.

## Pull requests

1. Open as **draft** early; mark ready when the checklist below is ticked.
2. Fill the PR template (`.github/pull_request_template.md`).
3. At least one approving review from a CODEOWNER of each touched area.
4. CI must be green. Never skip or disable a test to get green — fix it or
   raise it.
5. Squash-merge by default; the squash message follows Conventional Commits.

## Review checklist (author ticks, reviewer verifies)

- [ ] Does what the PR says; nothing unrelated.
- [ ] Tests added/updated and meaningful (not just coverage).
- [ ] `make lint typecheck test` green locally.
- [ ] Schemas changed? Backward-compatible per `schemas/README.md`, and every
      producer/consumer updated.
- [ ] Anything touching recorded data keeps `sim_time_us` as the ordering key.
- [ ] No new runtime internet dependency. No secrets. Large binaries via LFS.
- [ ] Docs updated (spec doc, README, `docs/CHANGELOG.md`); ADR written if a
      non-trivial decision was made.
- [ ] No third-party company/client names; no claims that anything beyond
      RAVEN is delivered.
- [ ] UI changes keep the Chakravyuha Dynamics logo placeholder on screen.

## Definition of done

Code + unit tests + doc update + `make test` green (see `CLAUDE.md`).

## Architecture Decision Records

Write an ADR (`docs/ADR/NNNN-title.md`, copy `0000-template.md`) when you:
choose a library/framework, change a data format or protocol, change a
deployment or security property, or pick between two reasonable designs a
future engineer might question. Status flows `Proposed → Accepted`
(→ `Superseded by NNNN`). ADRs are cheap; undocumented decisions are not.

## Local environment

See `docs/ONBOARDING.md` for the full day-1 setup. Short version:

```bash
make setup     # venv, Python + Node deps, git-lfs, .env
make dev       # core + terrain + lms services, waits until healthy
make test      # unit tests
```
