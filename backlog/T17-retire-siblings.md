---
id: T17
title: Deprecate ha-fluidra-local + addon; resolve PR #7 / #10
phase: 6-release
points: 2
status: todo
depends_on: [T16]
owner: agent
---
## Context
Decision 1: one integration. `Roagert/ha-fluidra-local` and `Roagert/fluidra-local-addon`
are superseded (the add-on's packaged cloud login is broken anyway: `FLUIDRA_CLIENT_ID` never set,
username/password env vars unused). PR #7 (`feat/fluidra-local-cli`) holds research docs +
CLIs; its capture docs were harvested by T13. PR #10 (@kifeo) fix was applied with credit in T07.

## Description
- In each sibling repo (branch `deprecate`, draft PR): README top banner "Deprecated —
  use Roagert/ha-fluidra-pool ≥ 2.0.0", with migration steps (remove old integration/add-on,
  install fluidra_pool, sign in). No code changes.
- `backlog/PR_NOTES.md`: drafted closing comments for PR #7 and PR #10 (not posted —
  lead/Thomas decides), including thanks to @kifeo.

## Acceptance criteria
- [ ] Two draft PRs opened in sibling repos (README only).
- [ ] `PR_NOTES.md` drafted. Archiving repos is left to Thomas (GitHub settings).
