---
id: T10
title: Climate entity correctness (modes, presets, hvac_action, errors)
phase: 4-entities
points: 5
status: done
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
- [x] Parametrized tests for every (power, mode) → (hvac_mode, preset) pair 0–6.
- [x] Tests: each `set_hvac_mode` sends exactly the expected PUT sequence; preset changes; `set_temperature(26.5)` → `(15, 265)`; failing PUT raises `HomeAssistantError`.
- [x] `hvac_action` tests incl. comp 11 absent → None.
- [x] unique_id unchanged; non-heat-pump devices get no climate entity.
- [x] Full suite passes. Closes #1 (draft a closing comment in the task log; do not post).

## Log
- `climate.py` 610 → 150 lines: `FluidraHeatPump(CoordinatorEntity)` per device with {13,14,15,19} (all devices, not just the first); translation key `heat_pump` = "Pool heat pump", so the entity_id stays `climate.<device>_pool_heat_pump` for fresh installs too (test); unique_id unchanged; device_info = identifiers + manufacturer + name (same values sensor.py writes). Unavailable after a failed poll or when a poll no longer lists the device (HA computes `preset_modes` even then, so `_value` tolerates it).
- Modes/presets/commands as specified; HEAT/COOL/AUTO always send the smart mode (resets boost/silence, per spec). Preset still shown while off; `preset_modes` follows the family (auto → `[smart]`, unknown mode → `[]`, so HA rejects). `turn_on` = 13→1 only (HA's default would set heat); `turn_off` = HA default (`set_hvac_mode(off)`). Commands run in order via `async_set_component`; the first failure raises `HomeAssistantError` and skips the rest. Auto + running: water ≤ setpoint → heating, else cooling; comp 11 marked UNVERIFIED in code.
- Not done: max 42.0 "if uiconfig reports it" — no uiconfig sample exists in the repo or its history, so the key is unknown; fixed 15.0–40.0. Revisit with U03's diagnostics download (it includes uiconfig).
- T16 CHANGELOG (breaking): presets `Smart Auto/Smart Heating/…` (7) → `smart/boost/silence` + hvac_mode; climate attributes removed: `component_id`, `temperature_component_id`, `target_temp_component_id`, `power_component_id`, `available_modes`, `device_id`, `last_update`, `alarm_status`, `has_error`, `has_critical_error`, `has_flow_error`, `error_code/message`, `warning_code/message`, `smart_auto_*`, `temperature_difference`, `deadband`; alarms no longer force off; step 0.1 → 0.5, min 8.1 → 15.0; name "Pool Heat Pump" → "Pool heat pump". Doc drift: PROTOCOL.md's mode table (0 Off, 1 Heat, …) contradicts README facts.
- Shim/const removed: `set_component_value`, `set_power_value`, `set_temperature_value`, `schedule_quick_update`; `CRITICAL_ERROR_CODES`, `FLOW_ERROR_CODES`, `SMART_AUTO_*`. Left for T11: coordinator `consumer_data`, `user_profile_data`, `pool_status_data`, `user_pools_data`, `device_id`, `devices`, `device_components_data`, `device_uiconfig_data`, `error_information`, `_legacy_device`, `_alarm_text`; `__init__` `hass.data[DOMAIN]` + "no devices → False" + unload pop; `ERROR_CODES` (sensor.py and the shim import it).
- Tests: `tests/test_climate.py` (43), mutation-checked (power before mode, swallowed failure, comp 11 absent → heating, unique_id, heat-pump filter, auto compare, `_attr_name = None`, missing en.json entity each fail a test). 105 passed. hassfest not run locally; new strings checked by hand against hassfest `translations.py` @2026.2.3.
- Issue #1 draft (post once T11 lands; not posted): "Fixed for the next release: the climate entity now reads the mode directly — Smart heating → Heat, Smart cooling → Cool, Smart heating/cooling → Auto, each with preset Smart/Boost/Silence — and shows Off only when the pump is powered off (tested for all 7 modes, on and off). The '… Data' sensors that only said 'Available' are gone: Settings → Devices & services → Fluidra Pool → Download diagnostics gives the raw values with secrets redacted, and the error sensor is reworked in the same release. If your HPCIG 60 still shows a wrong mode, please reopen with that diagnostics file."
- Lead review: accepted; lead fix in same commit: AUTO hvac_action returns None (no TypeError) when water temp or setpoint is missing (+ test). Max 42 °C from uiconfig deferred until a real uiconfig sample (U03 diagnostics).
