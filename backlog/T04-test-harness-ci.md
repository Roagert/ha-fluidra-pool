---
id: T04
title: Test harness + CI (pytest, hassfest, HACS)
phase: 1-foundation
points: 3
status: todo
depends_on: [T02]
owner: agent
---
## Context
There are zero real tests; CI (`.github/workflows/validate.yml`) was deleted in `dbcf5dd`.
Every later task's acceptance criteria rely on `pytest` passing. A working venv recipe
from the review: HA 2026.2.x + `pytest-homeassistant-custom-component` works.
`ha-fluidra-local/tests/` has 9 behaviour tests worth using as style reference
(ignore its 23 text-search "tests" — don't copy that pattern).

## Description
- `requirements_test.txt`: pinned `pytest-homeassistant-custom-component` (pulls HA), `aioresponses`.
- `tests/conftest.py`: `enable_custom_integrations` autouse fixture; a fixture that
  returns canned JSON for devices/components (`tests/fixtures/components_amt.json`
  with the components listed in `backlog/README.md` — fake ids only, never real tokens).
- `tests/test_smoke.py`: config entry with mocked HTTP sets up and unloads cleanly
  against the **current** code (it may need `xfail` markers for known bugs — mark each
  with the task id that fixes it).
- `pyproject.toml` or `setup.cfg`: pytest `asyncio_mode=auto`, testpaths=tests.
- `.github/workflows/ci.yml`: jobs `pytest`, `hassfest` (home-assistant/actions/hassfest),
  `hacs` (hacs/action, category integration). On push + PR.

## Acceptance criteria
- [ ] `python -m pytest -q` passes locally in a fresh venv built from `requirements_test.txt` (document the 3 commands in CLAUDE.md "how to run tests").
- [ ] Smoke test proves setup→unload with no real network (`pytest-socket` blocks it).
- [ ] CI workflow YAML is valid (`python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/ci.yml'))"`).
- [ ] No real device ids/emails/tokens in fixtures (use `TEST000001`).

## Out of scope
Fixing integration bugs (later tasks). hassfest/HACS may fail until T16 fixes the manifest — that's expected; note it.
