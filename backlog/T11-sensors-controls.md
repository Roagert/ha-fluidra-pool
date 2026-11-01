---
id: T11
title: Sensors, power switch, no-flow binary sensor; drop raw-JSON sensors
phase: 4-entities
points: 5
status: todo
depends_on: [T10]
owner: agent
---
## Context
`sensor.py` has 6 "* Data" diagnostic sensors that show "Available" instead of values
(issue #1), a refresh button (redundant with `homeassistant.update_entity`), and
chlorinator sensors whose uiconfig lookup can never resolve (always unavailable).
`ha-fluidra-local` has a working power `switch.py` (optimistic state) and a no-flow
`binary_sensor.py` (component 28) — port, but build unique IDs from the device id (theirs
are hardcoded to `LG24440781`). Issue #2 ("entity no longer provided") was caused by
entities silently disappearing — this time list removals in CHANGELOG (T16).

## Description
Per heat-pump device:
- sensors (unique_id `fluidra_{id}_<key>`): `water_temperature` (19, keep id), `air_temperature` (62),
  `target_temperature` (15), `wifi_rssi` (1, diagnostic, dBm, disabled by default), `error_information`
  (keep id; value from the device's real error component if identified — else show
  "ok"/raw value and mark unverified).
- `switch`: power (13), unique_id `fluidra_{id}_power`.
- `binary_sensor`: no-flow (28) `problem` class — only if component 28 present; verify meaning against PROTOCOL notes, mark unverified otherwise.
- Device info: manufacturer Fluidra, model from type/SKU (5/6), sw_version (4), serial (3).
- Delete: 6 "* Data" sensors, chlorinator sensors (T12 replaces them generically), `button.py`, unused consts.
- All entities use `CoordinatorEntity` + `_attr_has_entity_name = True` + translation keys.

## Acceptance criteria
- [ ] Tests: each entity's value from fixture components; unavailable when component missing; switch on/off sends 13=1/0 and raises on failure.
- [ ] Existing unique IDs `water_temperature` and `error_information` preserved (test).
- [ ] `sensor.py` ≤ 150 lines; `button.py` gone; PLATFORMS = climate, sensor, switch, binary_sensor.
- [ ] List of removed entity unique-id suffixes written to the task log (for CHANGELOG).
- [ ] Full suite passes.
