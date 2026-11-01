---
id: T02
title: Repo hygiene — delete stale duplicates, dumps, junk
phase: 1-foundation
points: 3
status: todo
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
- [ ] `git ls-files` at repo root contains no `.py` files; no `__init__.py` outside `custom_components/` and `tests/`.
- [ ] `custom_components/fluidra_pool/` contains only integration runtime files.
- [ ] `docs/RE-*.txt` gone; `docs/RE-libapp.md` points to fluidra-re.
- [ ] `pre-commit run --all-files` passes (or the only failures are pre-existing style issues in files T05–T12 will rewrite — list them).
- [ ] `python3 -m py_compile custom_components/fluidra_pool/*.py` passes.
- [ ] Integration code itself is unchanged (`git diff --stat HEAD~1 -- custom_components/fluidra_pool/*.py` empty).

## Out of scope
Changing integration code. Rewriting docs content (T16).
