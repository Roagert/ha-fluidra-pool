---
id: T17
title: Deprecate ha-fluidra-local + addon; resolve PR #7 / #10
phase: 6-release
points: 2
status: done
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
- [x] Two draft PRs opened in sibling repos (README only).
- [x] `PR_NOTES.md` drafted. Archiving repos is left to Thomas (GitHub settings).

## Log
- `deprecate` branches (from `origin/main`, upstream unset, not pushed): ha-fluidra-local `29c0023`, fluidra-local-addon `7edea53`; README banner only (+18 / +22 lines, 0 removed), notes 2.0.0 is in progress (#11).
- Draft-PR box open: the lead pushes `deprecate` and opens both draft PRs.
- `backlog/PR_NOTES.md`: closing comments for #7 (harvested vs. dropped, from `git diff --stat origin/main...origin/feat/fluidra-local-cli`) and #10 (thanks @kifeo; fix in T07 with co-author credit), to post after #11 merges.
- PR #10's head is based on the pre-T01 history (14 commits / 42 files): close, don't merge (already tracked in T01/U01).
- Lead: pushed `deprecate` branches, opened draft PRs Roagert/ha-fluidra-local#1 and Roagert/fluidra-local-addon#1 (merge after 2.0.0 is released).
