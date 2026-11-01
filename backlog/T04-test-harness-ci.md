---
id: T04
title: Test harness + CI (pytest, hassfest, HACS)
phase: 1-foundation
points: 3
status: done
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
- [x] `python -m pytest -q` passes locally in a fresh venv built from `requirements_test.txt` (document the 3 commands in CLAUDE.md "how to run tests").
- [x] Smoke test proves setup→unload with no real network (`pytest-socket` blocks it).
- [x] CI workflow YAML is valid (`python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/ci.yml'))"`).
- [x] No real device ids/emails/tokens in fixtures (use `TEST000001`).

## Out of scope
Fixing integration bugs (later tasks). hassfest/HACS may fail until T16 fixes the manifest — that's expected; note it.

## Log
- Pins: pytest-homeassistant-custom-component 0.13.316 (HA 2026.2.3, Python ≥3.13.2 → CI uses 3.13), aioresponses 0.7.9, boto3 1.43.123 (current `auth.py` imports it; drop in T05). Suite passes in the existing venv and in a fresh venv built only from `requirements_test.txt`.
- Mocking: `mock_auth` patches `FluidraAuth.authenticate` (no boto3/DNS); `mock_api` serves canned REST via aioresponses; pytest-socket (enabled by the HA plugin) blocks real sockets. Legacy consumer/profile/pools endpoints get non-empty payloads to dodge the coordinator's 2 s retry sleeps.
- WS: chose to patch `_start_websocket` in the smoke test instead of a strict xfail — verified that without it `async_block_till_done()` hangs (>20 s, listener retries every 5 s; #9). An xfail would leave setup→unload unproven until T07; T07 removes the patch and adds the #9 regression test.
- Smoke test also asserts the three invariant unique IDs are registered.
- hassfest/HACS jobs are expected to fail until T16 fixes `manifest.json`/`hacs.json` (not run locally: no Docker daemon in this sandbox).
- Lead review: accepted; suite re-run in fresh venv-t04 → 1 passed. WS start is patched in the smoke test; T07 must remove that patch.
