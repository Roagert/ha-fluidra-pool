---
id: T03
title: Add Karpathy guidelines + ECC review agents
phase: 1-foundation
points: 1
status: done
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
- [x] The 6 files exist; each copied file carries source + MIT attribution.
- [x] `grep -rniE 'hook|npx|npm|mcp|80%' .claude/` returns nothing (or only harmless prose — list it).
- [x] No other files changed.

## Log
- 2026-11-01: Added CLAUDE.md (Karpathy verbatim + 15-line Project rules), verbatim SKILL.md, 4 ECC agents (upstream b38be6a; `model:` dropped).
- Trimmed: Django/FastAPI/Flask checks, ECC skill references, `pytest --cov`, npm/npx tooling, web-only security patterns; JS examples swapped for Python.
- Verified: acceptance grep exits 1 with no output; `git show --stat HEAD` lists only the 6 files + this task file.
- Lead review: accepted; softened python-reviewer description ("MUST BE USED…" → on-demand) so it does not auto-trigger on every Python edit.
