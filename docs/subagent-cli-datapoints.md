# Subagent datapoint/feature map and local CLI design

Date: 2026-05-15
Scope: design-only; no live writes performed. The goal is a transport-independent `fluidra-local` CLI/data model for the owner’s Fluidra/Amitime heat pump while reusing the cloud-confirmed component map and existing HA integration knowledge.

## 1. Sources reviewed

- `PROTOCOL_FINDINGS.md` — authoritative live/API component facts for `LG24440781`.
- `custom_components/fluidra_pool/*.py` — current HA entities, services, options, coordinator read/write behavior.
- `custom_components/fluidra_pool/services.yaml` — HA diagnostic service schema.
- `PROTOCOL.md` and `BACKLOG.md` — older notes and feature ideas; `PROTOCOL.md` contains an older/conflicting component-14 mode table, so prefer `PROTOCOL_FINDINGS.md` and current `climate.py`.
- `docs/subagent-lan-discovery.md`, `docs/subagent-ble-local.md`, `docs/subagent-udp-protocol.md` — current local-transport status.
- `fluidra_re_extraction_redacted.md` — app strings/assets for heat-pump UI and flow/no-flow hints.

## 2. Existing HA integration inventory

### Platforms/entities

- `climate.Pool Heat Pump`
  - Features: target temperature, preset mode, turn on, turn off.
  - HVAC modes: `auto`, `heat`, `cool`, `off`.
  - Preset modes mapped to component 14:
    - `Smart Heating` -> `0`
    - `Smart Cooling` -> `1`
    - `Smart Auto` -> `2`
    - `Boost Heating` -> `3`
    - `Silence Heating` -> `4`
    - `Boost Cooling` -> `5`
    - `Silence Cooling` -> `6`
  - Current temperature: component 19, raw `x0.1 °C`.
  - Target temperature: component 15, raw `x0.1 °C`.
  - Power: component 13, `0/1`.
  - Smart Auto action inference: compares target-current using `SMART_AUTO_DEADBAND = 1.0 °C`.
  - Exposes diagnostic attributes: component IDs, available modes, alarm/error/flow flags, Smart Auto delta/deadband.

- Sensors:
  - `Devices Data`: count/summary of devices, status, alarms/errors.
  - `User Profile Data`: diagnostic summary of `/generic/users/me`.
  - `Pool Status Data`: optional diagnostic summary if pool status endpoint is available.
  - `User Pools Data`: diagnostic summary of pool permissions/links.
  - `Device Components Data`: diagnostic component summary: type/status/value/unit/writable.
  - `Device UI Config Data`: diagnostic UI config presence/features/controls/display options.
  - `Error Information`: current alarm/error code/message/status/count.
  - `Water Temperature`: standalone component 19 sensor, raw `/10` °C.
  - Runtime-resolved chlorinator-style sensors from UI i18n keys, if present: pH, ORP, salinity, free chlorine. These are generic pool feature hooks, not confirmed heat-pump datapoints for this `amt` device.

- Button:
  - `Refresh All Data`: calls coordinator refresh and logs endpoint availability.

### HA service/options

- Service: `fluidra_pool.dump_api_data`
  - Registered handler logs latest coordinator data.
  - YAML schema has optional `device_id` and `include_raw`, but current handler ignores the fields and always logs the coordinator’s latest data.

- Config/options:
  - Required setup input: `username`, `password`.
  - Entry stores placeholder `device_id` until first update discovers the first actual device.
  - Options:
    - `update_interval`: 2 minutes minimum, 2 hours maximum, default 15 minutes.
    - `api_rate_limit`: 10/min minimum, 120/min maximum, default 60/min.

### Coordinator data/API shape

The coordinator already normalizes these logical collections:

- Account/user: `/generic/users/me`, legacy `/mobile/consumers/me`.
- Pools: `/generic/users/me/pools`, optional `/generic/pools/{pool_id}/status`.
- Devices: `/generic/devices`.
- Device components: `/generic/devices/{device_id}/components?deviceType=connected`.
- UI config: `/generic/devices/{device_id}/uiconfig?appId=iaq&deviceType=connected`.
- Writes: `PUT /generic/devices/{device_id}/components/{component_id}?deviceType=connected` with `{ "desiredValue": value }`.
- WebSocket cloud updates: `wss://ws.fluidra-emea.com?token=***`; subscribe with `subsDevice`; messages update component reported values.

## 3. Confirmed heat-pump datapoint map

Device: `LG24440781`, serial `LG24440781`, type `amt`, firmware `2.5.0`, LAN IP component value `192.168.1.11`, Wi-Fi module SN `BXWAB0603494724050`, SKU `1441`.

### Identity/system components

- `0` — operational hours counter, integer.
- `1` — Wi-Fi RSSI dBm, integer.
- `2` — LAN IP address, string.
- `3` — device serial number, string.
- `4` — firmware version, string.
- `5` — model/type code, string (`amt`).
- `6` — SKU, string (`1441`).
- `7` — Wi-Fi module serial, string.
- `8` — reserved/none.
- `9` — empty/unused string.
- `10` — connected accessories config JSON.

### Control/status components

- `11` — heat-pump active/running state. Known values: `0=idle`, `1=running`. Treat read-only until UI/config proves writability.
- `13` — power. Values: `0=off`, `1=on`. Confirmed write target.
- `14` — mode. Values:
  - `0=SmartHeat`
  - `1=SmartCool`
  - `2=SmartAuto`
  - `3=BoostHeat`
  - `4=SilenceHeat`
  - `5=BoostCool`
  - `6=SilenceCool`
- `15` — set temperature, integer raw `x0.1 °C`. Confirmed write target. Live/API range in `PROTOCOL_FINDINGS.md`: raw `150..420` (15.0..42.0 °C). Current HA UI has a safer/default max 40.0 °C and min comment from UI config (`component 81 = 7°C + factor`) but the code sets min 8.1 °C. For a CLI, use capability-discovered limits when available and default to conservative `15.0..40.0 °C` unless the user explicitly widens.
- `16` — target mode / auto sub-mode, observed `2`, meaning TBD. Treat read-only/unknown.
- `17` — timer/schedule flag, observed `0=off`. Treat read-only/unknown until schedule semantics are mapped.
- `18` — anti-freeze / silent flag, observed `0=off`. Treat read-only/unknown.

### Sensors/read-only temperatures

All are raw `x0.1 °C` unless later UI config says otherwise.

- `19` — water temperature; known current pool/water temp.
- `62` — ambient/outdoor air temp.
- `65` — temperature sensor 65, unidentified.
- `66` — temperature sensor 66, unidentified.
- `67` — temperature sensor 67, unidentified.
- `68` — temperature sensor 68, likely water-in or duplicate water path.
- `69` — temperature sensor 69, unidentified/possibly water path.
- `70` — temperature sensor 70, unidentified.

### Additional IDs/hints

- 83 total components were mentioned in live findings, but the committed `fluidra_debug_20260330_132940.json/txt` is currently empty/failed for components; rely on `PROTOCOL_FINDINGS.md` for the confirmed set above.
- `PROTOCOL.md` mentions UI-config-derived unknowns: `137`, `185`, `272` (`componentRead`), and `276` (`componentWrite`). These should be exposed by the CLI as unknown/discovered datapoints, not assigned heat-pump semantics until fresh raw UI/config data confirms names/ranges.
- Current HA `sensor.py` can resolve generic chlorinator measurements from UI i18n keys (`ph_key`, `orp_key`, `salinity_key`, `free_chlorine_key`). Keep this as a generic feature-discovery path, but do not assume they exist on this `amt` heat pump.

## 4. Flow-related data

No confirmed numeric flow-rate component was found in the existing heat-pump map or HA code.

Known flow evidence:

- Error codes in `const.py`:
  - `E001` — No water flow detected.
  - `E016` — Water flow switch error.
- `FLOW_ERROR_CODES = {E001, E016}` and climate attributes expose `has_flow_error` when those alarms are present.
- App/assets contain heat-pump no-flow UI hints, e.g. `assets/images/equipment/hpc/ic_no_flow.png`.
- No component name/string in the reviewed map identifies a flow rate, pump speed, L/min, m³/h, or gallons/min datapoint for this `amt` device.

Recommended CLI treatment:

- Expose flow as a derived status first:
  - `flow.ok`: true when no flow-related alarm and device not in critical flow error.
  - `flow.alarm_code`: `E001`/`E016` if present.
  - `flow.alarm_message`: mapped message.
- Do not claim or display a numeric flow measurement unless a future component/UI config/capture identifies one.
- Add a discovery query for candidate flow fields by scanning component metadata, UI i18n keys, and raw names for: `flow`, `no_flow`, `water_flow`, `pump`, `filtration`, `lpm`, `m3h`, `gpm`, localized equivalents where available.

## 5. Transport-independent local CLI data model

The CLI should separate canonical datapoints/features from transport adapters. Cloud REST/WS, local MQTT, BLE, and UDP should all implement the same interface:

```python
class FluidraAdapter:
    async def discover(self) -> DeviceInventory: ...
    async def read_components(self, device_id: str, ids: list[int] | None = None) -> ComponentSnapshot: ...
    async def read_component(self, device_id: str, component_id: int) -> ComponentValue: ...
    async def write_component(self, device_id: str, component_id: int, raw_value: int | str | bool, *, dry_run: bool) -> WriteResult: ...
    async def subscribe(self, device_id: str, ids: list[int] | None = None) -> AsyncIterator[ComponentEvent]: ...
```

### Canonical objects

```yaml
Device:
  id: string
  serial: string
  type: string
  model: string|null
  sku: string|null
  firmware: string|null
  lan_ip: string|null
  wifi_rssi_dbm: int|null
  pool_id: string|null
  transports:
    cloud_rest: available|unavailable|unknown
    cloud_ws: available|unavailable|unknown
    local_mqtt: available|auth_required|unavailable|unknown
    ble: provisioning_only|command_control|unavailable|unknown
    udp: available|unavailable|unknown

Datapoint:
  id: int
  key: string        # e.g. power, mode, set_temperature
  name: string
  access: read|write|readwrite|unknown
  type: int|string|json|enum|bool
  unit: string|null
  scale: number      # e.g. 0.1 for temperatures
  raw_value: any
  value: any         # scaled/decoded
  desired_value: any|null
  ts: int|null
  confidence: confirmed|inferred|unknown
  source: cloud_components|uiconfig|ha_code|mqtt|ble|udp|capture

Feature:
  key: string        # heatpump, flow_status, diagnostics, schedules
  datapoints: list[int]
  commands: list[string]
```

### Canonical feature keys for this device

- `identity`: components `0..10`.
- `heatpump.power`: component `13`.
- `heatpump.mode`: component `14`.
- `heatpump.set_temperature`: component `15`.
- `heatpump.water_temperature`: component `19`.
- `heatpump.ambient_temperature`: component `62`.
- `heatpump.extra_temperatures`: components `65..70`.
- `heatpump.running_state`: component `11`.
- `heatpump.flow_status`: derived from alarms `E001`/`E016`, not numeric.
- `diagnostics.components`: all raw components.
- `diagnostics.uiconfig`: UI/config-discovered controls/ranges/i18n names.
- `unknown`: components with observed values but no assigned semantic name.

## 6. Proposed `fluidra-local` command surface

All commands accept shared connection/config flags:

- `--device LG24440781` or default from config.
- `--config ~/.config/fluidra-local/config.toml`.
- `--adapter auto|cloud|mqtt|ble|udp|offline`.
- `--host 192.168.1.11`, `--port 1883` where local adapter needs it.
- `--format text|json|yaml`.
- `--raw` to show raw component values alongside decoded values.
- `--dry-run` default for any set/write during development.
- `--allow-write` required for real writes; absent by default.
- `--confirm` or interactive confirmation required for real writes.

### Account/device discovery

- `fluidra-local account show`
  - Shows user/profile and pool links via a capable adapter (cloud initially).
- `fluidra-local devices list`
  - Device IDs, serials, types, firmware, LAN IP, connectivity, pool IDs.
- `fluidra-local device show [DEVICE]`
  - Identity/system datapoints, transport availability, firmware, Wi-Fi RSSI.
- `fluidra-local discover local [DEVICE]`
  - Read-only LAN/MQTT/BLE/UDP capability probe.
  - For this heat pump, current best local lead is authenticated local MQTT on `192.168.1.11:1883`; anonymous MQTT is known to be denied.
- `fluidra-local discover features [DEVICE]`
  - Prints components and UI-config-derived names/ranges/access if known.
- `fluidra-local discover grep [DEVICE] flow pump temperature mode`
  - Searches raw component metadata/UI strings for candidate features.

### Reading datapoints/status

- `fluidra-local status [DEVICE]`
  - Human summary: power, mode, running state, current water temp, set temp, ambient temp, flow/alarm status, update age.
- `fluidra-local components list [DEVICE] [--known|--unknown|--writable|--raw]`
  - Full component inventory with decoded values where known.
- `fluidra-local component get [DEVICE] 19 [--raw]`
  - Single datapoint read.
- `fluidra-local temps [DEVICE]`
  - Lists component 19, 62, 65-70 with raw and decoded °C.
- `fluidra-local flow status [DEVICE]`
  - Derived no-flow / flow-switch alarm status. It should explicitly say `numeric flow rate: not discovered` until proven otherwise.
- `fluidra-local alarms [DEVICE]`
  - Current alarm/warning list and decoded severity/message.
- `fluidra-local watch [DEVICE] [--components 13,14,15,19]`
  - Subscribe/watch updates over WS/MQTT/BLE when adapter supports it; otherwise poll safely.

### Heating/settings commands

These are the user-facing canonical commands. Initially they should run as dry-run unless explicit write flags are passed.

- `fluidra-local heat status [DEVICE]`
- `fluidra-local heat on [DEVICE]`
  - Write component 13 -> `1`.
- `fluidra-local heat off [DEVICE]`
  - Write component 13 -> `0`.
- `fluidra-local heat mode [DEVICE] smart-heat|smart-cool|smart-auto|boost-heat|silence-heat|boost-cool|silence-cool`
  - Write component 14.
- `fluidra-local heat set-temp [DEVICE] 29.0C`
  - Convert to raw `290`, write component 15.
- `fluidra-local heat set [DEVICE] --mode smart-auto --temp 29.0 --power on`
  - Multi-command plan; show exact component writes and execute sequentially only when allowed.

### Debug/offline commands

- `fluidra-local decode component --id 15 --raw 290`
  - Offline decode using data model.
- `fluidra-local encode component --key set_temperature --value 29.0`
  - Offline encode; useful for adapters/tests.
- `fluidra-local plan write [DEVICE] --component 15 --value 290`
  - Validates and displays write plan without sending.
- `fluidra-local import cloud-dump FILE.json`
  - Import/redact raw cloud dump for offline feature mapping.
- `fluidra-local pcap analyze FILE.pcapng`
  - Future decode-only transport reverse engineering; never sends packets.

## 7. Minimum read/write set for heating control

### Minimum reads

Required for safe display/control:

- Device identity: ID/SN/type/firmware, components `2`, `3`, `4`, `5`, `6`, `7` where available.
- Component `13`: power.
- Component `14`: mode.
- Component `15`: set temperature.
- Component `19`: water temperature.
- Component `11`: running state, if present.
- Alarm/error data: device alarms plus decoded `E001`/`E016` flow status and critical alarm set.

Useful additional reads:

- Component `1`: Wi-Fi RSSI.
- Component `62`: ambient temperature.
- Components `65..70`: extra diagnostic temperatures.
- UI config: min/max/step/access/i18n names for every component.
- Unknown/readable components for discovery (`137`, `185`, `272`, `276` if still present in UI config).

### Minimum writes

For heat-pump control, only these component writes are justified by current confirmed evidence:

- `13`: power `0` or `1`.
- `14`: mode enum `0..6`.
- `15`: set temperature raw integer, value in °C multiplied by 10.

Do not write components `11`, `16`, `17`, `18`, `81`, `82`, `137`, `185`, `272`, `276`, or any unknown discovered IDs until UI/config or captured official app behavior proves semantics and ranges.

## 8. Guardrails/ranges for safe CLI operation

Default policy: read-only. Real writes require `--allow-write` and confirmation. The CLI should make the write plan visible before sending.

### General write guardrails

- Dry-run by default for all `set`, `on`, `off`, `mode`, and raw component writes until the project intentionally flips the default.
- Refuse raw writes unless `--component` is in an explicit allowlist or `--unsafe-raw-write` is provided.
- Always read current state first and display current -> desired delta.
- If current state has `has_critical_error` or flow alarm (`E001`, `E016`), refuse power-on/mode/set-temp writes unless `--override-critical-alarm` is supplied.
- Rate-limit writes and follow with a readback/subscribe wait to verify `reportedValue`/`desiredValue` convergence.
- Do not send local MQTT publishes, BLE writes, or UDP packets until topic/frame semantics are confirmed. Discovery commands must be read-only.
- Redact tokens, MQTT passwords, UDP keys, HMACs, access codes, and raw authenticated packet bytes by default.

### Component-specific ranges

- Power component `13`:
  - Allowed raw values: `0`, `1` only.
- Mode component `14`:
  - Allowed raw values: `0..6` only, with the confirmed mapping from `PROTOCOL_FINDINGS.md`/`climate.py`.
- Temperature setpoint component `15`:
  - Raw integer = `round(celsius * 10)`.
  - UI step: `0.1 °C` internally; optionally allow display rounding to `0.5 °C` if user prefers.
  - Default safe CLI range: `15.0..40.0 °C`.
  - Protocol-confirmed broader range: `15.0..42.0 °C`; allow `40.1..42.0` only if the device’s UI config/range explicitly confirms it or user passes `--allow-extended-temp`.
  - Reject values below 15.0 °C by default despite the HA min-temp comment, because the live `PROTOCOL_FINDINGS.md` range says 15.0 °C lower bound.

## 9. Adapter implications

### Cloud adapter

- Known working for REST reads/writes and WebSocket subscribe.
- Should be the reference implementation for the canonical data model.
- The CLI can reuse endpoint constants and mappings from HA but should avoid HA-specific entity abstractions.

### Local MQTT adapter

- LAN discovery found `tcp/1883` open on `192.168.1.11`; anonymous MQTT is refused (`Not authorized`).
- Implement only after credentials/topic structure are known.
- Initial commands should be `discover local` and `watch/read` subscriptions, not publishes.
- Adapter must translate MQTT topic/payloads into the same `ComponentValue` objects.

### BLE adapter

- BLE provisioning SPP service is confirmed in API/app strings, but command/control for this exact `amt` instance is unproven.
- Treat BLE as `provisioning_only|unknown` until passive scan and cloud shape checks prove `MobileCommandAndControlBle` or equivalent.
- No connection/pairing/GATT write in default discovery.

### UDP adapter

- App has UDP command-control support, but `commandAndControl.localUdp` was not present for this `amt` device and LAN UDP probes did not expose a readable service.
- Keep UDP decode/probe tooling offline/read-only unless a cloud `localUdp` object or official-app capture proves host/port/key/framing.

## 10. Recommended implementation order

1. Create a standalone `fluidra_local.model` module with the datapoint registry above and encode/decode helpers for components `13`, `14`, `15`, `19`, `62`, `65..70`, plus unknown passthroughs.
2. Implement `cloud` adapter first as a known-good reference, but keep the CLI name transport-neutral.
3. Implement `status`, `components list/get`, `temps`, `flow status`, `alarms`, and `discover features` as read-only commands.
4. Add write planning for `heat on/off/mode/set-temp` that prints the component writes but defaults to dry-run.
5. Add guarded cloud writes for the three confirmed write datapoints only after explicit user approval.
6. Add local MQTT discovery once credentials are found; start with read/subscribe only.
7. Add BLE/UDP only as decode/probe modules until transport semantics are confirmed.
