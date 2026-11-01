---
id: T18
title: Final review gate (security, silent failures, simplicity)
phase: 6-release
points: 3
status: done
depends_on: [T17]
owner: agent
---
## Description
Run the four `.claude/agents/` reviewers (python-reviewer, silent-failure-hunter,
security-reviewer, code-simplifier) as read-only passes over `git diff main...finalize-v1`
of `custom_components/`. Fix only confirmed findings (each with a test). Re-run
`gitleaks detect` over the branch. Measure: total integration LOC (target ≤ 900).

## Acceptance criteria
- [x] Findings list with verdicts in `backlog/REVIEW.md`; all confirmed blockers/majors fixed.
- [x] gitleaks clean; full suite + CI green.

## Log
- F1–F15 of `REVIEW.md` fixed; every behaviour change (F1–F11, F13) has a test that failed first.
- Full suite: 163 passed (was 138); ruff pyflakes rules clean.
- `gitleaks git` (full history, fresh clone) with `.gitleaksignore`: no leaks found.
- Integration LOC (`wc -l custom_components/fluidra_pool/*.py`): 1,134 (was 1,301 incl. `local_client.py`).
- Box 2 open: CI not run (not pushed); gitleaks and the suite are green locally.
- Lead review: accepted; CI on 84cb1de green (pytest 163, hassfest, HACS). LOC target re-scoped in REVIEW.md (1,134 incl. other-device support).
