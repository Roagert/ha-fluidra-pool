# Subagent Local MQTT Investigation — Fluidra/Amitime heat pump

Date: 2026-05-15T18:33:36+02:00
Target: `192.168.1.11` (`LG24440781`, `amt`, firmware `2.5.0`, WiFi module `BXWAB0603494724050`)
Scope: authenticated-local-MQTT discovery only. No MQTT publishes, no state changes, no real credential use, no secret disclosure.

## Executive summary

The local control/status path for this `amt` heat pump is most likely an authenticated MQTT broker on `192.168.1.11:1883`.

Confirmed:

- `tcp/1883` is open and speaks MQTT.
- Anonymous MQTT 3.1.1 and MQTT 5 are refused as not authorized.
- Additional safe MQTT 3.1.1 `CONNECT` variants using only public device identifiers, blank password, or a placeholder password were also refused with the same `Not authorized` result.
- No local HTTP service was found in the prior LAN scan, and prior TCP/UDP candidates for the older iQBridge/local-UDP path did not respond usefully.

Not yet known:

- The actual local MQTT username/password/token/certificate scheme.
- Topic names for status/control.
- QoS/retain behavior.
- Whether the local broker is intended for mobile-app local control, device-internal bridge/debug, factory/service tooling, or cloud/edge bridging.

Current best next step is to extract the full redacted cloud `device detail` and `uiconfig`/`commandAndControl` objects, then inspect any local MQTT credential fields or provisioning identifiers without exposing secret values.

## Evidence from LAN probing

Prior scan evidence from `docs/subagent-lan-discovery.md`:

- Host reachable: `192.168.1.11`.
- Only open tested TCP service: `1883`.
- HTTP/HTTPS/common alternative ports closed/refused.
- UDP candidates mostly ICMP unreachable/no-response.

Anonymous MQTT results already recorded:

```text
MQTT 3.1.1 anonymous CONNECT: CONNACK 20 02 00 05
Return code 5 = Not authorized

MQTT 5 anonymous CONNECT: CONNACK 20 03 00 87 00
Reason code 0x87 = Not authorized
```

Additional safe probes run in this pass used no real credentials and did not subscribe or publish. They only sent MQTT `CONNECT` and read `CONNACK`:

```text
anon-empty-clientid:          client_id=''                         username=None                   password=<none>        -> 20020005
anon-device-clientid:         client_id='LG24440781'               username=None                   password=<none>        -> 20020005
anon-wifi-clientid:           client_id='BXWAB0603494724050'       username=None                   password=<none>        -> 20020005
user-device-blankpass:        client_id='probe-LG24440781'         username='LG24440781'           password=<blank>       -> 20020005
user-wifi-blankpass:          client_id='probe-BXWAB0603494724050' username='BXWAB0603494724050'   password=<blank>       -> 20020005
user-device-placeholder:      client_id='probe-LG24440781'         username='LG24440781'           password=<placeholder> -> 20020005
```

Interpretation:

- The broker consistently rejects unauthenticated/incorrectly-authenticated clients.
- Device serial alone is not enough as username or client ID.
- WiFi module serial alone is not enough as username or client ID.
- A blank or obvious placeholder password is not accepted.
- The broker accepts TCP and MQTT framing but provides no banner or topic visibility before successful authentication.

## Artifact mining results

Artifacts inspected:

- `PROTOCOL_FINDINGS.md`
- `docs/subagent-lan-discovery.md`
- `docs/RE-libapp.md`
- `docs/RE-libapp-ghidra-strings.txt`
- `/home/roagert/projects/fluidra-re/EVALUATION.md`
- `/home/roagert/projects/fluidra-re/native/lib/arm64-v8a/libapp.so` printable strings
- `/home/roagert/projects/fluidra-re/fluidra_re_extraction_redacted.md`

### MQTT-specific strings

High-signal result: the Android app's Dart AOT strings contain only two direct MQTT strings:

```text
mqttConnectionFailed
mqtt_connection_failed
```

No explicit local MQTT topic strings were found in the app strings. In particular, no obvious `mqtt://`, topic templates, `mosquitto`, `$aws/things/...`, `$aws/things/.../shadow/...`, or local topic names were present in the string table.

Interpretation:

- The mobile app likely does not hardcode MQTT topics for this path.
- If the app uses MQTT directly, topic/client/auth material is generated dynamically, hidden in non-obvious Dart AOT code, or provided by an API response.
- It is also plausible the app never talks to the local broker directly; the broker may be primarily for the heat-pump WiFi module, service tooling, or a local/cloud bridge.

### AWS IoT / cloud hints

Existing documentation strongly supports a cloud MQTT/AWS IoT backend for the `amt` heat pump:

- `PROTOCOL_FINDINGS.md` says `amt` is direct MQTT to AWS IoT, not iQBridge RS local UDP.
- App strings include environment keys:
  - `fluidra-emea-fluidra-pool-prod`
  - `fluidra-emea-fluidra-pool-staging`
  - `fluidra-emea-fluidra-pool-dev`
  - `fluidra-emea-fluidra-pool-test`
- App strings include AWS/Cognito classes and identifiers:
  - `AWSCognitoIdentityProviderService.*`
  - `AwsClientCredentials`
  - `AwsException`
  - `AWSIdentification`
  - `AWSIdentification(sku:`
  - `AWSIdentification.fromJson`
- App strings include `ShadowService`, `ShadowTransport`, and `Shadow.fromJson`, but these appear in generic API/client/BLE models and are not enough to infer local MQTT topics.

Interpretation:

- The cloud side likely uses AWS IoT shadows or a Fluidra abstraction over shadows.
- The visible app control path remains REST + Fluidra WebSocket, not direct app-to-AWS-MQTT.
- The local broker on `1883` is probably a separate plaintext LAN broker requiring device-specific auth rather than AWS IoT mTLS (AWS IoT normally uses TLS `8883` or WebSocket `443`, not unauthenticated LAN `1883`).

### Device identity hints

Known identifiers from protocol findings/API:

- Device ID / serial: `LG24440781`
- Device type/model: `amt`
- SKU: `1441`
- Firmware: `2.5.0`
- WiFi module serial: `BXWAB0603494724050`
- LAN IP: `192.168.1.11`

Artifact strings suggest multiple identification models:

```text
AWSIdentification(sku:
FederatedIdentification(sku:
ManualIdentification(sku:
SerialNumber(shadow:
Networks(cloud:
NetworksCapabilities(cloud:
```

Safe probe result: neither the device serial nor WiFi module serial works by itself as anonymous client ID or username with blank/placeholder password.

Likely credential derivation inputs to investigate next:

- Device serial `LG24440781`
- WiFi module serial `BXWAB0603494724050`
- SKU `1441`
- A QR/HPC pairing code, if available from packaging/app/API
- Provisioning credentials stored on the module and/or returned by cloud during pairing
- A command-and-control object in cloud device detail/UI config

### Topic names, QoS, retain behavior

No local MQTT topic names, QoS values, or retain flags were confirmed.

Known non-MQTT cloud schemas that can guide topic decoding later:

Cloud WebSocket subscription:

```json
{
  "action": "subsDevice",
  "deviceType": "connected",
  "deviceId": "LG24440781"
}
```

Expected cloud WebSocket update shape:

```json
{
  "action": "command",
  "deviceId": "LG24440781",
  "deviceType": "connected",
  "componentId": "13",
  "reportedValue": 1
}
```

REST component read/write schema:

```json
{
  "id": 13,
  "reportedValue": 0,
  "ts": 1758877765
}
```

```json
{
  "desiredValue": 1
}
```

Likely local MQTT payloads, if exposed, may map to these fields:

- `deviceId`
- `deviceType=connected`
- `componentId` / `id`
- `reportedValue`
- `desiredValue`
- `ts`

But topic names and payload shape must be confirmed by read-only subscribe once valid credentials are known.

## Candidate local MQTT auth models

Ranked hypotheses:

1. Cloud/API-provisioned local MQTT credentials
   - Most likely if the mobile app can use LAN control.
   - Search target: full `device detail`, `/uiconfig`, and any `commandAndControl` object.
   - Preserve key names/object shape; redact values for fields like password, token, secret, key, cert, privateKey.

2. Device/module serial + derived password
   - Inputs may include heat-pump serial, WiFi module serial, SKU, QR/HPC pairing code, or local BLE access code.
   - Simple serial-only username/password tests failed.

3. Static vendor/service credentials
   - Possible but not supported by app strings; no obvious default credential strings found.
   - Do not brute force.

4. AWS IoT credentials reused locally
   - Less likely because local listener is plaintext `1883`, not TLS `8883`/`443`.
   - App strings do show AWS IoT/cloud/shadow concepts, but not local MQTT credentials.

5. Broker is internal/service-only and not intended for app local control
   - Possible because mobile app strings emphasize REST/WebSocket, BLE, and local UDP paths; direct MQTT strings are minimal.

## CLI design once credentials are known

Add a separate local MQTT CLI/probe before integrating into Home Assistant. It should default to read-only and require explicit opt-in for publish/control.

Suggested file later: `tools/fluidra_local_mqtt.py` or `scripts/local_mqtt_probe.py`.

### Phase 1: read-only connect and narrow subscribe

Inputs:

- `--host 192.168.1.11`
- `--port 1883`
- `--client-id fluidra-probe-<random>`
- `--username <from discovered auth material>`
- `--password-env FLUIDRA_LOCAL_MQTT_PASSWORD` or `--password-file` to avoid shell history
- `--topic <candidate topic>` repeatable
- `--timeout 30`
- `--max-messages 50`
- `--no-publish` default and enforced

Behavior:

1. Connect with MQTT 3.1.1 first; try MQTT 5 only if needed.
2. Subscribe to the narrowest candidate status topics first.
3. Print topic, QoS, retain flag, timestamp, and payload.
4. Attempt JSON decoding; if not JSON, print hex + safe printable text.
5. Never publish.
6. Redact configured secret fields in logs.

Initial topic strategy after credentials are known:

- First try exact/narrow topics inferred from API/traffic capture.
- If unknown, do a short, time-limited wildcard read:
  - `LG24440781/#`
  - `BXWAB0603494724050/#`
  - `amt/LG24440781/#`
  - `connected/LG24440781/#`
  - `devices/LG24440781/#`
  - Only use `#` briefly if the broker ACL allows it and no narrow topics produce data.

### Phase 2: map status schema

Correlate observed MQTT messages against known cloud components:

- `13`: power, `0/1`
- `14`: mode
- `15`: set temperature in tenths of °C
- `19`: water temperature in tenths of °C
- `1`: WiFi RSSI
- `2`: LAN IP
- `3`: device serial
- `4`: firmware
- `5`: model code
- `7`: WiFi module serial

Record:

- Topic names
- QoS delivered
- Retain flag
- Payload type/encoding
- Whether retained status is emitted immediately after subscribe
- Whether status changes appear without cloud polling

### Phase 3: command publish only after explicit approval

Publishing must remain disabled until:

1. Status topics are mapped.
2. Command topic and payload schema are confirmed from a reliable source.
3. User explicitly asks to test a specific command.
4. A dry-run mode prints exactly what would be published.

Command safety guardrails:

- Require `--allow-publish` and `--confirm-device LG24440781`.
- Require component allowlist, initially only low-risk known controls after approval:
  - `13` power
  - `14` mode
  - `15` setpoint
- Validate ranges locally:
  - Power: `0` or `1`
  - Setpoint: `150..420` tenths °C
  - Mode: known enum `0..6`
- Print the old cloud-reported value and intended new value before publishing.
- Prefer QoS/retain exactly as observed from official clients; never retain commands unless confirmed.

## Exact next steps

1. Extract full redacted API objects with existing Cognito/REST path:
   - `GET /generic/devices?deviceType=connected`
   - `GET /generic/devices/LG24440781?deviceType=connected`
   - `GET /generic/devices/LG24440781/uiconfig?appId=iaq&deviceType=connected`
   - `GET /generic/devices/LG24440781/components?deviceType=connected`

2. In those API responses, search for keys/objects including:
   - `commandAndControl`
   - `mqtt`
   - `localMqtt`
   - `broker`
   - `host`
   - `port`
   - `username`
   - `password`
   - `token`
   - `secret`
   - `key`
   - `cert`
   - `privateKey`
   - `clientId`
   - `thingName`
   - `shadow`
   - `aws`
   - `iot`
   - `localUdp`
   - `bleCommandAndControl`

3. Redact secret values but preserve object structure. Suggested redaction policy:
   - Keep key names.
   - Keep value type and length only for secrets, e.g. `"<redacted:str:32>"`.
   - Keep non-secret IDs like device serial, model, firmware, LAN IP.

4. If credentials are found, run read-only subscribe with narrow topics first. Do not publish.

5. If API does not expose local MQTT auth material, capture passive LAN traffic while opening the official app on the same WiFi network:
   - Capture only traffic to/from `192.168.1.11:1883`.
   - Do not publish from the probe machine.
   - Redact MQTT username/password and payloads containing tokens/secrets before writing notes.
   - If TLS is absent, MQTT CONNECT username/password may be visible in packet capture; handle as secret.

6. If app traffic capture shows no MQTT connection to `192.168.1.11:1883`, treat the local broker as not app-facing and focus on BLE/provisioning or cloud REST/WebSocket fallback.

## Bottom line

`192.168.1.11:1883` is a real authenticated local MQTT broker, but neither anonymous access nor obvious serial-based placeholder auth works. The Android app artifacts do not reveal hardcoded MQTT topics or credentials. The next productive step is not brute force; it is extracting/redacting the cloud command-and-control/device-detail objects or passively observing the official app to learn the legitimate local MQTT credential and topic scheme.
