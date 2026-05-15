# Local heatpump connection plan — 5-agent synthesis

Date: 2026-05-15
Device: Fluidra/Amitime `amt` heat pump, `LG24440781`, firmware `2.5.0`, LAN IP `192.168.1.11`

## Executive conclusion

Five independent approaches were tested/investigated. The most promising local path is **authenticated MQTT on `192.168.1.11:1883`**.

The previous local-UDP hypothesis is now low confidence for this specific `amt` heat pump. UDP appears real in the Fluidra app, but likely applies to iQBridge/Lumiplus/local-UDP capable devices, not necessarily this Amitime heat pump.

BLE is promising but currently looks provisioning-first. It may support command/control through the app's generic BLE stack, but it is not yet proven for this device in normal operation.

## Approach results

### 1. LAN service discovery

Report: `docs/subagent-lan-discovery.md`

Findings:

- `192.168.1.11` is reachable from this host on the LAN.
- Route/source: `wlp9s0`, source IP `192.168.1.62`.
- Exactly one tested TCP service was open:
  - `tcp/1883` — MQTT broker.
- HTTP/HTTPS/common web ports were closed/refused.
- Prior Fluidra/iQBridge UDP candidate ports did not return useful readable data.
- Anonymous MQTT is refused:
  - MQTT 3.1.1 return code `5`, not authorized.
  - MQTT 5 reason code `0x87`, not authorized.

Implication:

- Build around MQTT discovery next, not HTTP.

### 2. Static UDP protocol reverse engineering

Report: `docs/subagent-udp-protocol.md`

Findings:

- App strings strongly confirm a UDP stack exists:
  - `MobileCommandAndControlLocalUdp`
  - `sendUDPCommand`
  - `initUdpDeviceListener`
  - `FluidraMessageProtocol`
  - `MagicNumber`
  - `payloadIntBE`, `payloadIntLE`, `payloadString`
  - `hmac256`, `getCrc32Byte`
  - `udpKey`, `updateUPDkey`
- But for this known `amt` heat pump, prior cloud/device evidence did not expose `commandAndControl.localUdp`.
- Current `local_client.py` packet layout is a hypothesis and should not be trusted for writes.

Implication:

- Keep UDP as a decoder/probe research track only.
- Do not ship direct UDP writes until packet capture or exact protocol evidence exists.

### 3. BLE SPP/provisioning investigation

Report: `docs/subagent-ble-local.md`

Findings:

- Bluetooth tools and adapter are available.
- Passive BLE scan worked, but no advertisement obviously matched Fluidra/Amitime/known UUID/device serial.
- App/device evidence confirms BLE provisioning capabilities:
  - Service UUID: `4e7763c4-211b-47b8-88df-cd869df32c48`
  - RX UUID: `54c4dfef-4e04-4c42-9c33-06a6af86280c`
  - TX UUID: `760f6551-4156-4829-8bcc-62591b1eb948`
  - Protocol: SPP; variants `SPP8`, `SPP32`, `SPP8X`.
- Access-code/pairing gating is strongly indicated.

Implication:

- BLE is worth a second pass with `bleak` and the heat pump in provisioning/add-device mode.
- Treat BLE as unproven for local runtime datapoints/control until service enumeration and read-only handshake are confirmed.

### 4. Authenticated local MQTT investigation

Report: `docs/subagent-local-mqtt.md`

Findings:

- `tcp/1883` is confirmed MQTT and requires auth.
- Safe CONNECT variants using public identifiers only were refused:
  - anonymous client ID
  - device serial as client ID
  - WiFi module serial as client ID
  - serial/module serial as username with blank/placeholder password
- App strings did not reveal topic templates or credentials.
- Best next source for MQTT credentials/topics is the redacted full device detail/uiconfig/command-and-control cloud objects, or passive official-app/device traffic capture.

Implication:

- Local MQTT is the lead candidate.
- Need credentials and topic schema before a real CLI can subscribe/read.

### 5. Datapoint and CLI surface design

Report: `docs/subagent-cli-datapoints.md`

Confirmed useful datapoints:

- `13` — power, `0=OFF`, `1=ON`.
- `14` — mode:
  - `0` SmartHeat
  - `1` SmartCool
  - `2` SmartAuto
  - `3` BoostHeat
  - `4` SilenceHeat
  - `5` BoostCool
  - `6` SilenceCool
- `15` — set temperature, raw `x0.1 °C`.
- `19` — water temperature, raw `x0.1 °C`.
- `62` — ambient/outdoor temperature, raw `x0.1 °C`.
- `65..70` — additional temperature sensors, raw `x0.1 °C`.
- `0..10` — identity/system fields.
- `11` — running/active state.

Flow:

- No confirmed numeric flow-rate component was found.
- Model flow as status/alarm for now, likely from `E001` / `E016` no-flow style errors and app no-flow UI hints.

CLI direction:

- Use one transport-independent data model with adapters for cloud, MQTT, BLE, and UDP.
- Default to read-only/dry-run.
- Only allow writes to confirmed components `13`, `14`, and `15` after explicit `--allow-write`/confirmation.

## Recommended implementation sequence

1. **Create `fluidra-local discover`**
   - Ping/ARP target.
   - TCP scan known ports.
   - MQTT CONNACK probe.
   - BLE passive scan if adapter exists.
   - No writes.

2. **Create `fluidra-local cloud-dump --redact`**
   - Fetch device detail, components, uiconfig, command-and-control shape.
   - Redact tokens/passwords/IDs where needed.
   - Preserve field names and transport sections.
   - Goal: find local MQTT credentials/topics or confirm they are absent.

3. **Create `fluidra-local mqtt probe`**
   - Accept user-supplied credentials or extracted local credentials.
   - Connect to `192.168.1.11:1883`.
   - Subscribe read-only to a narrow candidate set once topics are known.
   - Never publish by default.

4. **Create `fluidra-local status`**
   - Read using the best available transport.
   - Print power, mode, setpoint, water temp, ambient temp, active state, alarms, and flow/no-flow status.

5. **Create guarded write commands**
   - `heat on/off`
   - `heat mode <smart-heat|smart-cool|smart-auto|boost-heat|silence-heat|boost-cool|silence-cool>`
   - `heat set-temp <15.0..42.0>`
   - Require explicit write flag and confirmation.

## Open blockers

- We do not yet have local MQTT credentials or topic schema.
- The committed debug JSON does not contain the expected full 83-component dump; `PROTOCOL_FINDINGS.md` remains the authoritative map for now.
- UDP packet format is not confirmed.
- BLE runtime control is not confirmed.
- Flow measurement is not confirmed as a numeric datapoint.

## Files produced by the five subagents

- `docs/subagent-lan-discovery.md`
- `docs/subagent-udp-protocol.md`
- `docs/subagent-ble-local.md`
- `docs/subagent-local-mqtt.md`
- `docs/subagent-cli-datapoints.md`

## Safety policy for next work

- Read-only probes are allowed.
- No MQTT publishes, UDP command packets, BLE writes, or heat-pump setting changes without explicit approval.
- Do not log or print credentials/tokens/raw authenticated packets.
- Writes must be dry-run by default and restricted to known safe components/ranges.
