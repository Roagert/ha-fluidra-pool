# Fluidra Local CLI

`fluidra_local.py` is a standalone, read-only-first CLI for investigating the Fluidra/Amitime heat pump and validating the canonical component/datapoint model.

## Current target

- Device: `LG24440781`
- Device type: `amt` Amitime / Swim & Fun inverter heat pump
- LAN IP: `192.168.1.29` from Home Assistant `device_tracker.fluidra` as of 2026-05-15
- MAC: `ac:15:18:98:15:f0`
- Read-only probe result: ping reachable, but common candidate TCP ports were closed, including `1883`

## Historical correction

`192.168.1.11` / MAC `02:0e:8a:69:3d:61` was previously assumed to be the Fluidra device. Packet capture proved it is the Home Assistant host / local Mosquitto broker:

- `homeassistant.local`
- Home Assistant websocket traffic on `8123`
- Matter/HAP/Music Assistant advertisements
- MQTT broker on `1883`

Do **not** use MQTT for Fluidra control. MQTT findings from `192.168.1.11` are Home Assistant/Mosquitto noise.

## Safety model

The CLI currently does **not**:

- send UDP control packets
- write BLE characteristics
- publish MQTT messages
- change heat-pump settings
- apply firewall/router rules

It can safely:

- probe LAN reachability and TCP ports for the actual Fluidra IP
- decode component JSON into friendly heat-pump status
- validate whether a future write would be inside the confirmed safe component/range set
- generate router/firewall instructions as text only

## Usage

From the repository root, discover the actual Fluidra host:

```bash
python3 scripts/fluidra_local.py --host 192.168.1.29 discover
```

Decode a component JSON dump:

```bash
python3 scripts/fluidra_local.py status components.json
```

Validate a future write without sending it:

```bash
python3 scripts/fluidra_local.py validate-write 13 1     # power ON
python3 scripts/fluidra_local.py validate-write 14 2     # SmartAuto
python3 scripts/fluidra_local.py validate-write 15 290   # 29.0 °C
```

Generate an internet-isolation plan:

```bash
python3 scripts/fluidra_local.py --host 192.168.1.29 firewall-plan \
  --mac ac:15:18:98:15:f0 \
  --router openwrt \
  --lan-cidr 192.168.1.0/24
```

The firewall plan is intentionally output-only. Do not apply it until a working non-cloud control path exists, otherwise cloud/app control may be lost.

## Confirmed cloud datapoints

These are confirmed from `uiconfig` plus the live `components` dump for `LG24440781` / `BXWAB0603494724050`:

- `13`: power, `0=OFF`, `1=ON`
- `14`: mode
  - `0` Smart Heating
  - `1` Smart Cooling
  - `2` Smart Heating / Cooling
  - `3` Boost Heating
  - `4` Silence Heating
  - `5` Boost Cooling
  - `6` Silence Cooling
- `15`: set temperature, raw `x0.1 °C`
- `19`: pool/water temperature, raw `x0.1 °C`
- `28`: no-flow alarm, `1=No Flow`, `0=OK`
- `67`: air temperature, raw `x0.1 °C`
- `68`: water inlet temperature, raw `x0.1 °C`
- `69`: water outlet temperature, raw `x0.1 °C`
- `74`: supply voltage
- `80`: effective/current mode
- `81`: minimum setpoint °C
- `82`: maximum setpoint °C
- `11`: running/active state

Component `62` appears in older captures but is not used by the confirmed iAquaLink+ `uiconfig` for this device. Treat it as unknown/hidden config until proven.

## Confirmed cloud control

See `/home/roagert/projects/fluidra-re/REST_CONTROL_SURFACE.md` for the full confirmed cloud API spec.

Confirmed write shape:

```http
PUT /generic/devices/LG24440781/components/{componentId}?deviceType=connected
Authorization: Bearer <Cognito AccessToken>
Content-Type: application/json
```

```json
{ "desiredValue": 0 }
```

## Local research tracks

### UDP

The Flutter app contains generic local UDP command/control strings (`MobileCommandAndControlLocalUdp`, `sendUDPCommand`, `udpKey`, `hmac256`, CRC/magic helpers), but current `amt` API snapshots do not expose `commandAndControl.localUdp` for this heat pump. Treat UDP as research-only until packet capture or Dart AOT function recovery proves the exact protocol.

### BLE

The device API confirms BLE SPP provisioning:

- Service UUID: `4e7763c4-211b-47b8-88df-cd869df32c48`
- RX UUID: `54c4dfef-4e04-4c42-9c33-06a6af86280c`
- TX UUID: `760f6551-4156-4829-8bcc-62591b1eb948`
- Protocol: `SPP`
- Pairing mode: `auto`

Runtime BLE control is not proven. Only passive scan / read-only GATT discovery should be used unless explicitly approved.

## Current blocker

There is no confirmed local control transport yet. The next steps are:

1. Confirmed cloud REST CLI is implemented in `scripts/fluidra_cloud.py` and documented in `docs/fluidra-cloud-cli.md`.
2. Use `fluidra-re` / Ghidra / Dart AOT tooling to recover UDP/BLE protocol details.
3. Prefer router/AP packet capture while the official app performs a harmless command.
4. Avoid MQTT entirely for Fluidra.
