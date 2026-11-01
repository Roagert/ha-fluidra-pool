---
id: T11
title: Sensors, power switch, no-flow binary sensor; drop raw-JSON sensors
phase: 4-entities
points: 5
status: done
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
- [x] Tests: each entity's value from fixture components; unavailable when component missing; switch on/off sends 13=1/0 and raises on failure.
- [x] Existing unique IDs `water_temperature` and `error_information` preserved (test).
- [x] `sensor.py` ≤ 150 lines; `button.py` gone; PLATFORMS = climate, sensor, switch, binary_sensor.
- [x] List of removed entity unique-id suffixes written to the task log (for CHANGELOG).
- [x] Full suite passes.

## Log
- `entity.py` (54): `FluidraEntity` (unique id `fluidra_{id}_{key}`, device info, availability, `_value`) + `heat_pumps()`; climate uses it (152 → 129). Per heat pump: sensors `water_temperature` 19, `air_temperature` 62, `target_temperature` 15, `wifi_rssi` 1 (diagnostic, disabled); switch `power` 13; binary sensor `no_flow` 28 (only if reported; meaning per ha-fluidra-local README, UNVERIFIED here). Each unavailable while its component is missing.
- Device info (all entities): Fluidra, name, model = device `type`, model_id = SKU (6), sw_version (4), serial (3). Components 3/4/6 verified for `amt` only.
- `error_information` (unique id kept) now on EVERY device, so non-heat-pump users keep it: state `ok`, or `alarm` while the cloud's device record lists `alarms` (the list the pre-1.0 sensor read; format never captured, UNVERIFIED), attribute `alarms` = raw list. `ERROR_CODES` deleted.
- Removed unique-id suffixes (CHANGELOG): `devices_data`, `pool_status_data`, `device_components_data`, `device_uiconfig_data` (+ `user_profile_data`, `user_pools_data`, gone since T07), `chlorinator_ph_key`, `chlorinator_orp_key`, `chlorinator_salinity_key`, `chlorinator_free_chlorine_key`, `refresh_all_data` (button); `water_temperature` on devices without heat-pump components 13/14/15/19 (it showed component 19 ÷ 10 on any device, cf. #4 404.2 °C).
- Also breaking: `error_information` states `No Error`/`<code> — <text>`/`Error` → `ok`/`alarm`; its attributes `title`, `text`, `error_code`, `alarm_status`, `alarm_count`, `device_id`, `timestamp`, `last_update` removed.
- Shim gone (coordinator properties, `_legacy_device`, `_alarm_text`, `hass.data[DOMAIN]`, unload pop); no devices → entry loads with no entities (test). Consts dropped: `ERROR_CODES`, `CONF_DEVICE_ID`, `CONF_COMPONENT_ID`. Fixture gained component 6 (`1441`, as on the real device).
- Tests: `tests/test_entities.py` (23); 13 mutations each fail a test. 129 passed. hassfest not run (no docker daemon; running HA's hassfest script was denied); new keys/values checked against its translations.py @2026.2.3 rules.
- Lead review: accepted (entity/sensor/switch/binary_sensor read; 129 passed).
