---
id: T01
title: Purge secrets and PII from git history
phase: 0-safety
points: 3
status: done
depends_on: []
owner: agent
---
## Context
The Fluidra password, full Cognito JWTs (access/id/refresh), email, full name, Cognito
`sub`, pool id and country are committed and pushed. Files (all revisions):
`PROTOCOL_FINDINGS.md` (password line ~294, PII table ~line 20), `tasks/TASK-DYN-001.md`,
`fluidra_auth_test_20250714_165653.log`, `tests/fluidra_enhanced_test_20250829_132530.log`,
`tests/fluidra_enhanced_test_20250829_132617.log`. Remote branches affected: `main`,
`feat/fluidra-local-cli` (PR #7). Thomas approved a history rewrite + force-push.
Other repos were scanned: clean.

## Description
In a **fresh mirror clone in the scratchpad** (never in `/home/user/ha-fluidra-pool`):
1. `git filter-repo --invert-paths` for the 3 `.log` files and `tasks/TASK-DYN-001.md`.
2. `git filter-repo --replace-text` with a rules file (kept in the scratchpad, never
   committed) that replaces: the password (all variants, with/without `!`), the email,
   the full name, the Cognito sub, the pool id → `***REDACTED***`.
3. Rewrite both `main` and `feat/fluidra-local-cli`.
4. Verify, then report. **Do not push** — the lead pushes after checking.

## Acceptance criteria
- [x] `git rev-list --all | xargs git grep -nE '<password>|eyJraWQiOi|<email>'` in the rewritten clone returns nothing.
- [x] The 4 removed files do not exist in any commit (`git log --all -- <path>` empty).
- [x] Commit count per branch unchanged except commits that only touched removed files.
- [x] `custom_components/` tree at the tip of `main` is byte-identical to before (`git diff <old-main> <new-main> -- custom_components` empty).
- [x] Report lists old→new tip SHAs for both branches and the exact push commands.

## Out of scope
Deleting RE dumps or other cleanup (T02). Changing the password (U01).

## Verify
Commands above, run in the scratch clone.

## Log
- 2026-11-01: rewritten in a scratch clone; lead re-verified (all-blob scan, removed
  paths, `custom_components` tree `fc5df8a` unchanged), then force-pushed with lease:
  `main` bfb14c4 → 5f6799a, `feat/fluidra-local-cli` f3ec897 → 573f973. `dev`/`master`
  scanned clean (predate the leaks), left untouched. Commit 4b7340e's message also
  redacted. Remaining exposure outside our control: fork `kifeo/ha-fluidra-pool`,
  GitHub-cached `refs/pull/10`, and the author email in commit metadata → U01.
