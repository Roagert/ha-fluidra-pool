---
id: T12
title: Other devices — no crash, no bogus values, generic sensors
phase: 4-entities
points: 5
status: done
depends_on: [T11]
owner: agent
---
## Context
Issues from users we can't test:
- #5 Tecno LC2 / Zodiac IQ 12: "Component 13 NOT FOUND", uiconfig 500, sensors unknown.
- #4 Blue Connect Gold: uiconfig 500; water temp shows 404.2 °C (wrong scaling/sentinel).
- #8 Ei2q Evo: pH/pH-setpoint stuck at 2.54 (raw 254 = probable "no data" sentinel), ORP mixes with setpoint, temp/salinity 0.0.
- #3 Irripool iSalt: only generic entities.
Thomas chose: graceful handling + diagnostics (T09) + generic sensors; proper mapping
only after reporters share diagnostics.

## Description
- Heat-pump entities only for devices that have components 13, 14, 15 and 19.
- For every other device: create a **disabled-by-default** generic numeric sensor per
  component listed in uiconfig with a recognisable unit (when uiconfig is available), else none;
  always create a `component_count` diagnostic sensor so the device appears with useful info.
- Value sanity guard (one small function): temperatures outside −30…80 °C → unavailable;
  pH outside 0…14 → unavailable; raw 254/255/65535 sentinels → unavailable.
- No exceptions anywhere when components/uiconfig are missing (log once at debug).
- `backlog/ISSUE_REPLIES.md`: draft (not post) a short reply per issue #3 #4 #5 #8 asking
  for the diagnostics download from the new release.

## Acceptance criteria
- [x] Tests with fixtures `components_chlorinator.json` (incl. 254 pH), `components_blueconnect.json` (incl. 4042 temp), `components_no13.json`: setup succeeds, no climate entity, sentinel/out-of-range → unavailable, no error logs.
- [x] uiconfig 500 → setup still succeeds (test).
- [x] `ISSUE_REPLIES.md` exists with 4 drafts.
- [x] Full suite passes.

## Log
- `sensor.py`: `celsius()` guard on every °C×10 sensor (water/air/target, heat pumps): outside −30…80 °C → unavailable (`available` = value not None). Each non-heat-pump device: `component_count` (diagnostic, enabled, "Components") + per component reporting an int/float (not bool) at setup a raw `Component <id>` sensor, unique id `fluidra_<id>_component_<cid>`, disabled, no unit/scaling/state class; 254/255/65535 → unavailable.
- Deviation: not "listed in uiconfig with a recognisable unit" — no uiconfig sample exists, so generic sensors come from components alone (lead's call). No pH guard: there is no pH sensor (would be dead code).
- `water_temperature` NOT restored on non-heat-pumps with component 19 (2 lines, but the guard only rejects out-of-range values: #8's 0.0 °C or any in-range value with another meaning would still show as °C). Raw value stays reachable as `Component 19`.
- `api.py`: uiconfig ≥ 400 → one debug line per device (fetched once). caplog: no WARNING/ERROR with heat pump + 4 fake devices (chlorinator, blueconnect, no13, empty `[]`), all uiconfig 500; HA's custom-integration notice excepted.
- Tests: `tests/test_other_devices.py` (2); conftest serves `components_<type>.json` per device and now holds `entity_registry_enabled_by_default`; test_entities gained guard rows, other-device test updated. Fixtures invented from the issue texts (real ids unknown). 12 mutations each fail a test. 137 passed.
- Box 1 nuance: the Blue Connect 4042 is never shown as a temperature (raw, unitless, disabled `Component 19`); the out-of-range rule is tested with 4042 on the heat pump's sensors.
- Not done: an HTTP error on one device's components still fails the whole poll (T07 note; no report shows it, and skipping the device would drop a heat pump's entities after a transient error at startup). Climate `current_temperature` is not guarded.
- T16 CHANGELOG: added `component_count`, `component_<id>` (non-heat-pump devices); nothing removed. Replies drafted in `backlog/ISSUE_REPLIES.md`, not posted.
- Lead review: accepted; lead fix in same commit: one device failing its components read no longer fails the whole poll (only all-failed → UpdateFailed) + test.
