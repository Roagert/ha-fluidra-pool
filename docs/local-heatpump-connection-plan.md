# Fluidra heat pump connection plan — corrected synthesis

Date: 2026-05-15
Device: Fluidra/Amitime `amt` heat pump, `LG24440781`, firmware `2.5.0`

## Critical correction

`192.168.1.11` is **not** the Fluidra heat pump. A packet capture showed that host is Home Assistant/Mosquitto (`homeassistant.local`, Home Assistant websocket on `8123`, Matter/HAP/Music Assistant, MQTT `1883`).

The actual Fluidra device is tracked by Home Assistant as:

- Entity: `device_tracker.fluidra`
- IP on 2026-05-15: `192.168.1.29`
- MAC on 2026-05-15: `ac:15:18:98:15:f0`

Do not pursue MQTT for this heat pump. The earlier MQTT path was Home Assistant broker noise.

## Executive conclusion

The confirmed control path for this heat pump is **Fluidra cloud REST** with AWS Cognito access tokens and component `desiredValue` writes.

Local UDP and BLE remain research tracks:

- UDP: generic Fluidra app support exists (`MobileCommandAndControlLocalUdp`, `sendUDPCommand`, `udpKey`, HMAC/CRC helpers), but current `amt` API snapshots do **not** expose `commandAndControl.localUdp` for LG24440781.
- BLE: SPP provisioning is confirmed by device capabilities, but runtime BLE control is not proven for this `amt` device.
- MQTT: omit entirely for Fluidra control.

## Confirmed cloud API

Base:

```text
https://api.fluidra-emea.com
```

Auth:

```text
Authorization: Bearer <Cognito AccessToken>
```

Observed token TTL: approximately 300 seconds.

Confirmed endpoints:

```text
GET /generic/devices/LG24440781?deviceType=connected
GET /generic/devices/LG24440781/components?deviceType=connected
GET /generic/devices/LG24440781/uiconfig?appId=iaq&deviceType=connected
PUT /generic/devices/LG24440781/components/{componentId}?deviceType=connected
```

PUT body:

```json
{ "desiredValue": 0 }
```

Confirmed important components:

- `13` — power, `0=OFF`, `1=ON`
- `14` — mode
  - `0` SmartHeat
  - `1` SmartCool
  - `2` SmartAuto
  - `3` BoostHeat
  - `4` SilenceHeat
  - `5` BoostCool
  - `6` SilenceCool
- `15` — set temperature, raw `x0.1 °C`
- `19` — water temperature, raw `x0.1 °C`
- `0..10` — identity/system fields
- `11` — running/active state

## Approach results

### 1. LAN service discovery

Corrected findings:

- `192.168.1.29` is the Fluidra heat pump IP from Home Assistant tracker.
- Read-only probe: ping reachable.
- Common candidate TCP ports were closed, including `1883`.
- `192.168.1.11:1883` is Home Assistant/Mosquitto, not Fluidra.

Implication:

- Do not build a Fluidra MQTT path.
- Use LAN probing only to support UDP/BLE research and always confirm the current IP from Home Assistant first.

### 2. Static UDP protocol reverse engineering

Report: `/home/roagert/projects/fluidra-re/LOCAL_UDP_FINDINGS.md`

Findings:

- App strings strongly confirm a generic UDP stack exists:
  - `MobileCommandAndControlLocalUdp`
  - `sendUDPCommand`
  - `udpService`
  - `udpKey`
  - `updateUPDkey`
  - `generateWorkingKey`
  - `FluidraMessageProtocol`
  - `MagicNumber`
  - `payloadIntBE`, `payloadIntLE`
  - `hmac256`, `getCrc32Byte`
- Ghidra headless/raw string search found offsets/addresses, but plain Ghidra did not recover useful Dart AOT xrefs.
- Exact packet layout and key derivation remain unknown.
- Current `amt` snapshots do not prove UDP is enabled for LG24440781.

Implication:

- Keep UDP as research only.
- Next evidence layer should be router/AP capture or Dart AOT-aware recovery, not guessed packets.

### 3. BLE SPP/provisioning investigation

Confirmed from device API:

- BLE protocol: `SPP`
- Pairing mode: `auto`
- Service UUID: `4e7763c4-211b-47b8-88df-cd869df32c48`
- RX UUID: `54c4dfef-4e04-4c42-9c33-06a6af86280c`
- TX UUID: `760f6551-4156-4829-8bcc-62591b1eb948`

Static app evidence also shows generic runtime BLE command/control classes, SPP framing variants, CRC, and access-code machinery. Current `amt` snapshots expose BLE under provisioning capabilities only; runtime BLE control is not proven.

Implication:

- Safe BLE tool work: parse provisioning block, passive advertisement scan, optional read-only GATT service discovery only with explicit user approval.
- No BLE writes until protocol and state impact are known.

### 4. Cloud REST tool direction

Report: `/home/roagert/projects/fluidra-re/REST_CONTROL_SURFACE.md`

Recommended `fluidra-re` CLI shape:

```bash
fluidra-re auth login --username "$FLUIDRA_USERNAME" --password "$FLUIDRA_PASSWORD" --json
fluidra-re cloud device --device-id LG24440781 --device-type connected --json
fluidra-re cloud components --device-id LG24440781 --device-type connected --json
fluidra-re cloud uiconfig --device-id LG24440781 --app-id iaq --device-type connected --json
fluidra-re cloud component --device-id LG24440781 --component-id 13 --device-type connected --json
fluidra-re cloud set-power --device-id LG24440781 --off --device-type connected --confirm --json
fluidra-re cloud set-temperature --device-id LG24440781 --celsius 26.0 --device-type connected --confirm --json
```

Safety options:

- `--dry-run` by default for writes during development
- `--confirm` / `--yes` for writes
- `--poll-after-put`
- `--redact` by default
- never print tokens or private raw payloads unless explicitly requested and redacted

## Recommended implementation sequence

1. Implement `fluidra-re cloud` first:
   - Cognito login/token cache with expiry margin
   - device/components/uiconfig GETs
   - guarded `desiredValue` PUTs for components `13`, `14`, `15`
   - status rendering from component map

2. Add `fluidra-re analyze-apk`:
   - scan `libapp.so` for UDP/BLE high-signal strings
   - emit offsets and confidence levels
   - optionally run the Ghidra raw string script

3. Add `fluidra-re ble inspect-snapshot`:
   - parse device/uiconfig snapshots for provisioning vs runtime BLE config
   - classify `ble_role` without touching the device

4. Add `fluidra-re capture-plan`:
   - print router/AP tcpdump filters for the current Fluidra IP
   - explicitly target UDP/BLE research only
   - no MQTT suggestions

5. Only after packet/code proof: consider experimental local UDP/BLE adapters.

## Open blockers

- No confirmed local UDP packet format or `udpKey` for LG24440781.
- No proof that BLE runtime control is enabled for this `amt` device.
- No numeric flow-rate component confirmed.
- Access-token refresh needs robust implementation for unattended CLI use.

## Safety policy for next work

- Read-only probes are allowed.
- No UDP command packets, BLE writes, or heat-pump setting changes without explicit approval.
- Cloud PUTs must be dry-run or explicitly confirmed.
- Do not log or print credentials, bearer tokens, `udpKey`, raw authenticated packets, or unredacted private payloads.
- MQTT is not a Fluidra path here and should not appear in future command suggestions.
