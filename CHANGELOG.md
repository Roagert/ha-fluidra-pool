# Changelog

## 2.0.0

A rewrite: one small cloud-push integration (REST + WebSocket), every device on the account,
MFA login and diagnostics. Requires Home Assistant 2025.3 or newer.

### Breaking

- **Removed entities** (Home Assistant shows them as "no longer provided"; delete them under
  Settings → Entities). Unique ids are `fluidra_<device id>_<suffix>`:

  | Suffix | Was |
  |---|---|
  | `devices_data`, `user_profile_data`, `pool_status_data`, `user_pools_data`, `device_components_data`, `device_uiconfig_data` | the six "… Data" sensors (they only showed "Available"; use Download diagnostics) |
  | `chlorinator_ph_key`, `chlorinator_orp_key`, `chlorinator_salinity_key`, `chlorinator_free_chlorine_key` | guessed chlorinator sensors (never resolved, or showed wrong values) |
  | `refresh_all_data` | the Refresh All Data button (use `homeassistant.update_entity`) |
  | `water_temperature` on devices that are not heat pumps | showed component 19 ÷ 10 on any device (e.g. 404.2 °C) |
  | `climate_heatpump` on devices that are not heat pumps | the thermostat of a device without heat-pump components |

  "Heat pump" = a device that reports components 13, 14, 15 and 19. On heat pumps the climate,
  water temperature and error information entities keep their unique ids.
- **Climate**: the seven presets (`Smart Auto`, `Smart Heating`, `Smart Cooling`,
  `Boost Heating`, `Silence Heating`, `Boost Cooling`, `Silence Cooling`) are now the HVAC
  mode Heat / Cool / Auto plus preset `smart` / `boost` / `silence` (Auto: `smart` only).
  Target range 15–40 °C in 0.5 °C steps (was 8.1 °C minimum, 0.1 °C steps). Alarms no longer
  force the mode to Off. Name "Pool Heat Pump" → "Pool heat pump" (entity id unchanged).
  Removed attributes: `component_id`, `temperature_component_id`, `target_temp_component_id`,
  `power_component_id`, `available_modes`, `device_id`, `last_update`, `alarm_status`,
  `has_error`, `has_critical_error`, `has_flow_error`, `error_code`, `error_message`,
  `warning_code`, `warning_message`, `smart_auto_*`, `temperature_difference`, `deadband`.
- **Error information**: states `No Error` / `<code> — <text>` / `Error` → `ok` / `alarm`;
  attributes `title`, `text`, `error_code`, `alarm_status`, `alarm_count`, `device_id`,
  `timestamp`, `last_update` replaced by `alarms` (the raw list). The invented error codes
  (E001–W005) are gone.
- The options and the `fluidra_pool.dump_api_data` service are removed (see Removed).
- The config entry is migrated to version 2 automatically (login kept; the stored device,
  component and polling options are dropped). Its title `Fluidra Pool (<e-mail>)` becomes
  `Fluidra Pool`, so the e-mail no longer shows in the log; a title you chose is kept.

### Fixed

- #1: Smart heating/cooling showed as Off. The climate entity reads the mode directly and
  shows Off only when the pump is powered off; Heat / Cool / Auto now really change the mode
  (Cool used to keep heating); `hvac_action` is idle / heating / cooling.
- #2: entities no longer disappear silently: unique ids of the kept entities are unchanged
  and every removed entity is listed above.
- #9: Home Assistant startup was blocked for about 5 minutes by the WebSocket listener; it
  now runs as a background task. Thanks to @kifeo for the fix (PR #10).
- Devices other than the heat pump (#3 #4 #5 #8) set up without errors and no longer show
  guessed values (no "Component 13 NOT FOUND", no 404.2 °C, no pH 2.54; temperatures outside
  −30…80 °C show as unavailable); a failed read of one device no longer fails the others,
  and the cloud's HTTP 500 for a UI config is ignored.
- Login: the access token (about 5 minutes) is renewed with the refresh token instead of a
  full password login on every check; a network error now retries instead of asking you to
  log in again.
- A failed command shows an error instead of looking successful.
- A device the cloud reports offline shows as unavailable instead of with its last values.
- `climate.set_temperature` with `hvac_mode` now also sets the mode.

### Added

- Login with two-step verification (authenticator app or SMS code), and a reauthentication
  flow when Fluidra rejects the stored login.
- Download diagnostics, with password, tokens, e-mail, names, IP/MAC and Wi-Fi details removed.
- Entities for every device on the account, not only the first one.
- Heat pumps: **Power** switch, **No flow** binary sensor (component 28, if reported),
  **Air temperature**, **Target temperature** and **Wi-Fi signal** (disabled) sensors;
  device info with model, model id (SKU), firmware and serial.
- Other devices: **Components** sensor and a disabled **Component N** sensor with the raw
  value of each numeric component, until a proper mapping exists.
- A log warning when WebSocket push stays unavailable (values then update by polling every
  5 minutes), and a log message when it is back.

### Removed

- Options flow (update interval, API rate limit): polling is every 5 minutes, with WebSocket
  push in between.
- Service `fluidra_pool.dump_api_data`: use Settings → Devices & services → Fluidra Pool →
  ⋮ → Download diagnostics.
- Refresh All Data button: use the `homeassistant.update_entity` action.
- The `boto3` / `pycognito` dependency (login is plain HTTPS now).
- The unused local UDP stub `local_client.py`.
