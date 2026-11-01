---
id: T18
title: Final review gate (security, silent failures, simplicity)
phase: 6-release
points: 3
status: todo
depends_on: [T17]
owner: agent
---
## Description
Run the four `.claude/agents/` reviewers (python-reviewer, silent-failure-hunter,
security-reviewer, code-simplifier) as read-only passes over `git diff main...finalize-v1`
of `custom_components/`. Fix only confirmed findings (each with a test). Re-run
`gitleaks detect` over the branch. Measure: total integration LOC (target ≤ 900).

## Acceptance criteria
- [ ] Findings list with verdicts in `backlog/REVIEW.md`; all confirmed blockers/majors fixed.
- [ ] gitleaks clean; full suite + CI green.
