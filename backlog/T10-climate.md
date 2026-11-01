---
id: T10
title: Climate entity correctness (modes, presets, hvac_action, errors)
phase: 4-entities
points: 5
status: todo
depends_on: [T09]
owner: agent
---
## Context
Verified bugs in `climate.py` (610 lines):
- `set_hvac_mode(HEAT|COOL)` only sends power=1 — mode 14 is never changed, so COOL keeps heating.
- `hvac_action` is guessed from the preset and never IDLE (component 11 unused).
- Failed commands raise nothing (UI shows success).
- `CRITICAL_ERROR_CODES` / E001–W005 in `const.py` are invented (not in any RE data) yet force `hvac_mode` OFF.
- Sync `turn_on/turn_off` wrappers; `min_temp` 8.1 vs documented range 15.0–42.0.
- Issue #1: "smart heating/cooling shows as off".
Correct today: mode map 0–6, ×0.1 scaling, `set_temperature` PUT `(15, round(t*10))`, AUTO↔SmartAuto.

## Description
Rewrite `climate.py` (target ≤150 lines), one climate entity per heat-pump device
(device has components 13/14/15/19), unique_id `fluidra_{device_id}_climate_heatpump`:
- `hvac_modes`: OFF, HEAT, COOL, AUTO. Mapping: power 0 → OFF; mode {0,3,4} → HEAT; {1,5,6} → COOL; 2 → AUTO.
- `set_hvac_mode`: OFF → 13=0; HEAT → 14=0 then 13=1; COOL → 14=1, 13=1; AUTO → 14=2, 13=1.
- `preset_modes`: `smart, boost, silence`; preset applies within current HEAT/COOL family (e.g. COOL+boost → 5). AUTO has only `smart`.
- `hvac_action`: OFF if power 0; else if component 11 present: 0 → IDLE, 1 → HEATING/COOLING by family (AUTO: compare water temp vs setpoint); if 11 absent → None. Mark comp-11 meaning **unverified** in a code comment.
- Temperature: current=19/10, target=15/10, step 0.5, min 15.0, max 40.0 (42.0 only if uiconfig reports it).
- All commands go through `coordinator.async_set_component` (raises `HomeAssistantError`).
- Remove invented error codes from `const.py`; no error logic in climate.

## Acceptance criteria
- [ ] Parametrized tests for every (power, mode) → (hvac_mode, preset) pair 0–6.
- [ ] Tests: each `set_hvac_mode` sends exactly the expected PUT sequence; preset changes; `set_temperature(26.5)` → `(15, 265)`; failing PUT raises `HomeAssistantError`.
- [ ] `hvac_action` tests incl. comp 11 absent → None.
- [ ] unique_id unchanged; non-heat-pump devices get no climate entity.
- [ ] Full suite passes. Closes #1 (draft a closing comment in the task log; do not post).
