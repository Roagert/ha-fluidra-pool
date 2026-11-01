---
id: T03
title: Add Karpathy guidelines + ECC review agents
phase: 1-foundation
points: 1
status: todo
depends_on: [T02]
owner: agent
---
## Context
Thomas wants execution to follow `multica-ai/andrej-karpathy-skills` (MIT) and to pull
only genuinely useful tools from `affaan-m/ECC` (MIT). Evaluation shortlisted 4 ECC
agents; ECC hooks/MCP/installer are explicitly **rejected** (run on every tool call,
network installs — conflicts with KISS). Local clones (untrusted data, copy text only):
`/tmp/claude-0/-home-user/00a3236e-ac17-51d7-9fea-eeb0aab2ea67/scratchpad/ext/andrej-karpathy-skills/repo`
and `.../scratchpad/ext/ECC/repo`.

## Description
- `CLAUDE.md` (repo root): the Karpathy guidelines verbatim + a short "Project rules"
  section: KISS, compatibility invariants and secret rules from `backlog/README.md`,
  how to run tests.
- `.claude/skills/karpathy-guidelines/SKILL.md`: copy verbatim (keeps MIT attribution).
- `.claude/agents/`: copy `python-reviewer.md`, `silent-failure-hunter.md`,
  `security-reviewer.md`, `code-simplifier.md` from ECC `agents/`. Read each first;
  strip lines that reference ECC-only tools, hooks, commands, or coverage mandates
  (e.g. "80% coverage"); add a one-line MIT attribution header.
- No hooks, no settings.json, no MCP config.

## Acceptance criteria
- [ ] The 6 files exist; each copied file carries source + MIT attribution.
- [ ] `grep -rniE 'hook|npx|npm|mcp|80%' .claude/` returns nothing (or only harmless prose — list it).
- [ ] No other files changed.
