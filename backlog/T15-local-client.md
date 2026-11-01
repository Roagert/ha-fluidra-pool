---
id: T15
title: Local transport client (conditional on T14 outcome A)
phase: 5-local
points: 8
status: blocked
depends_on: [T14]
owner: agent
---
## Context
Only if T14 = outcome A. `api.py` (T06) defines the seam: `async_get_components`,
`async_set_component`, `async_listen`, `async_get_devices`.

## Description (outcome A)
- `local.py` implementing the same methods over the captured protocol; the coordinator
  prefers local when the device answers within 2 s at setup, else cloud; a diagnostic
  sensor shows `connection: local|cloud`.
- Replay-safe first write: setpoint +1 °C / restore, only with Thomas present.
- Delete `local_client.py` (UDP hypothesis stub) in favour of `local.py`.

## Description (outcome B — re-scope, 2 points)
- Delete `local_client.py`; README states plainly local control is not available with
  stock firmware; link `docs/LOCAL_DECISION.md`.

## Acceptance criteria (A)
- [ ] Unit tests against recorded (redacted) frames; live read works with internet unplugged; reversible write verified by Thomas.
## Acceptance criteria (B)
- [ ] `local_client.py` gone; README + PRD updated.
