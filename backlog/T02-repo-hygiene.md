---
id: T02
title: Repo hygiene — delete stale duplicates, dumps, junk
phase: 1-foundation
points: 3
status: done
depends_on: [T01]
owner: agent
---
## Context
`hacs.json` has `content_in_root: false`, so only `custom_components/fluidra_pool/` is
shipped. The repo root holds stale copies of the integration (8 `.py` files plus
`manifest.json`, `services.yaml`, `translations/`, `icon.svg`, `logo.png`); root
`coordinator.py` still uses the wrong WebSocket header auth. A root `__init__.py` breaks
pytest collection. `docs/RE-libapp-functions.txt` and `docs/RE-libapp-ghidra-strings.txt`
are ~219k lines of Ghidra output from the proprietary app (noise + legal risk; the RE
workspace `Roagert/fluidra-re` is the right home). `custom_components/fluidra_pool/`
ships `tests/`, `README.md`, `.gitignore` to users. `tests/test_auth_*.py` are
interactive `input()` scripts that write DEBUG botocore logs (would capture passwords).
`.pre-commit-config.yaml` references a missing `tests/bandit.yaml`; no secret scanning.
`fluidra_debug.py` uses header WS auth and CLI-arg credentials. `tasks/TASKS.md` links
9 missing files.

## Description
Delete (normal commit, no history rewrite):
- root: `__init__.py auth.py button.py climate.py config_flow.py const.py coordinator.py sensor.py manifest.json services.yaml icon.svg logo.png translations/`
- `custom_components/fluidra_pool/{tests/,README.md,.gitignore}`
- `tests/test_auth_direct.py tests/test_auth_standalone.py tests/__init__.py`
- `docs/RE-libapp-functions.txt docs/RE-libapp-ghidra-strings.txt` (leave a one-line pointer in `docs/RE-libapp.md` to `Roagert/fluidra-re`)
- `fluidra_debug.py` (replaced by diagnostics in T09)
- `tasks/` and root `BACKLOG.md` (superseded by `backlog/`)
Fix `.pre-commit-config.yaml`: drop the broken bandit hook, add `gitleaks` (or
`detect-secrets`) hook. Extend `.gitignore`: `*.log`, `fluidra_debug_*`, `*.pcap*`, `captures/`, `.venv/`.

## Acceptance criteria
- [x] `git ls-files` at repo root contains no `.py` files; no `__init__.py` outside `custom_components/` and `tests/`.
- [x] `custom_components/fluidra_pool/` contains only integration runtime files.
- [x] `docs/RE-*.txt` gone; `docs/RE-libapp.md` points to fluidra-re.
- [ ] `pre-commit run --all-files` passes (or the only failures are pre-existing style issues in files T05–T12 will rewrite — list them).
- [x] `python3 -m py_compile custom_components/fluidra_pool/*.py` passes.
- [x] Integration code itself is unchanged (`git diff --stat HEAD~1 -- custom_components/fluidra_pool/*.py` empty).

## Out of scope
Changing integration code. Rewriting docs content (T16).

## Log
- Deleted 28 files / 223,787 lines: root stale copies (3,327; root `coordinator.py`/`sensor.py` were older, header-WS-auth versions, rest identical), RE dumps (218,766), `custom_components/fluidra_pool/{tests,README.md,.gitignore}` (426), `tests/` scripts (363), `fluidra_debug.py` (516), `tasks/` + `BACKLOG.md` (389; TASKS.md actually linked 12 missing files, not 9).
- `.pre-commit-config.yaml`: bandit → gitleaks `v8.30.1` (tag verified via `git ls-remote`); gitleaks hook passes, but it scans only staged changes. `.gitignore` extended; `docs/RE-libapp.md` points to `Roagert/fluidra-re`.
- pre-commit box left unticked: whitespace/EOF/black/flake8/isort fail in integration files (T05–T12) and also in out-of-scope files: `LICENSE`, `README.md`, `hacs.json`, `docs/{troubleshooting,usage}.md`, `scripts/ghidra_*.py`, `backlog/progress.py`. Autofixes reverted, not committed.
- `gitleaks git` (full history): 2 `gcp-api-key` hits in the deleted RE dumps (commit 85954865), still in history; T01's purge did not cover them.
- Root `README.md` has unresolved merge-conflict markers (lines 1/68/305) that `check-merge-conflict` does not catch outside a merge; T16 rewrites it.
- Lead review: accepted. pre-commit failures are pre-existing style issues (LICENSE,
  README, hacs.json, docs, scripts/ghidra_*, backlog/progress.py) — not blocking. The
  `AIzaSy…` hits in history are Fluidra's own Firebase key shipped in the public APK, not a
  user secret; removed from tip, history left as is.
