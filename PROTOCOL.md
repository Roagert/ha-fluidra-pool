# Fluidra cloud protocol

What the integration talks to, and what is known about the rest. Sources: a live API capture
of an Amitime heat pump (`amt`) on 2026-03-30, the integration's own tests, and reverse
engineering of the Android app's `libapp.so` on 2026-03-29 ([docs/RE-libapp.md](docs/RE-libapp.md);
raw dumps and tooling in [`Roagert/fluidra-re`](https://github.com/Roagert/fluidra-re)).

Status labels: **confirmed** = seen on the wire; **unverified** = expected, not yet seen;
**hypothesis** = read from the app binary only.

## 1. Authentication — confirmed

AWS Cognito, plain JSON over HTTPS (no SDK needed):

| Field | Value |
|---|---|
| Endpoint | `POST https://cognito-idp.eu-west-1.amazonaws.com/` |
| Headers | `Content-Type: application/x-amz-json-1.1`, `X-Amz-Target: AWSCognitoIdentityProviderService.<Action>` |
| User pool / client id | `eu-west-1_OnopMZF9X` / `g3njunelkcbtefosqm9bdhhq1` |
| Login | `InitiateAuth`, `AuthFlow: USER_PASSWORD_AUTH`, `USERNAME` = account e-mail, `PASSWORD` |
| MFA (some accounts) | reply `ChallengeName: SOFTWARE_TOKEN_MFA` or `SMS_MFA` + `Session` → `RespondToAuthChallenge` with `<challenge>_CODE` |
| Refresh | `InitiateAuth`, `AuthFlow: REFRESH_TOKEN_AUTH`, `REFRESH_TOKEN` |
| Access token TTL | about 300 s |

The access token is used for both REST and WebSocket.

## 2. REST — confirmed

Base `https://api.fluidra-emea.com`, header `Authorization: Bearer <access token>`.

| Method | Path | Notes |
|---|---|---|
| GET | `/generic/devices?deviceType=connected` | the account's devices |
| GET | `/generic/devices/{id}?deviceType=connected` | one device |
| GET | `/generic/devices/{id}/components?deviceType=connected` | all components (83 on `amt`) |
| GET | `/generic/devices/{id}/components/{cid}?deviceType=connected` | one component |
| PUT | `/generic/devices/{id}/components/{cid}?deviceType=connected` | body `{"desiredValue": <value>}` |
| GET | `/generic/devices/{id}/uiconfig?appId=iaq&deviceType=connected` | UI layout; HTTP 500 for some devices |
| GET | `/generic/users/me`, `/generic/users/me/pools` | profile, pools (not used by the integration) |

A component is `{"id": 15, "reportedValue": 290, "desiredValue": 290, "ts": 1758204079}`
(`desiredValue` is not always present; `ts` in seconds). The PUT replies with the same
shape, and is accepted (stored by the cloud) while the device is offline.

## 3. WebSocket — connect and subscribe confirmed, push unverified

- URL `wss://ws.fluidra-emea.com?token=<access token>`: the token goes in the **query
  string**, not in a header. (The app also knows `test.`, `stage.` and `dev.` hosts.)
- Subscribe, once per device:
  `{"action": "subsDevice", "deviceType": "connected", "deviceId": "<device id>"}`
- Reply: `{"statusCode": 200, "action": "subsDevice", "body": "{\"deviceId\":\"<device id>\",\"deviceType\":\"connected\",\"message\":\"OK\"}"}`
  (`body` is a JSON string).
- Push, **unverified** (the device was offline during the capture):
  `{"action": "command", "deviceId": "<device id>", "deviceType": "connected", "componentId": "13", "reportedValue": 1}`.
  The integration merges a string `body` into the message and accepts `ts` in s or ms.
- Hypothesis (app binary): commands over the socket as
  `{"action": "command", "commandId": "<component id>", "desiredValue": <value>}`. Not used;
  the integration sends commands by REST PUT.

## 4. Components of the `amt` heat pump — confirmed unless marked

Temperatures are °C × 10 (`290` = 29.0 °C).

| ID | Meaning | Example / range |
|---|---|---|
| 0 | operating hours counter | `409` |
| 1 | Wi-Fi RSSI, dBm | `-82` |
| 2 | LAN IP of the device (redacted in diagnostics) | string |
| 3 | serial number (= device id) | string |
| 4 | firmware version | `2.5.0` |
| 5 | model code | `amt` |
| 6 | SKU | `1441` |
| 7 | Wi-Fi module serial | string |
| 8, 9 | reserved / empty | |
| 10 | connected accessories | `[{"p":"nn","id":"nn_1"}]` |
| 11 | running state — **unverified** | 0 idle, 1 running |
| 13 | **power** (read/write) | 0 off, 1 on |
| 14 | **mode** (read/write) | see below |
| 15 | **setpoint** (read/write) | 150–420 (15.0–42.0 °C) |
| 16 | target / auto sub-mode — unknown | `2` |
| 17 | timer / schedule flag — unknown | `0` |
| 18 | anti-freeze / silent flag — unknown | `0` |
| 19 | **water temperature** | `131` = 13.1 °C |
| 28 | no-flow error — **unverified** (per `ha-fluidra-local`) | 0 = flow OK |
| 62 | outdoor air temperature | `320` = 32.0 °C |
| 65–70 | further temperature sensors — meaning unknown | °C × 10 |
| 137, 185, 272, 276 | referenced by the UI config — meaning unknown | |

Mode (component 14), as captured, and how the integration shows it:

| Value | Mode | HA HVAC mode / preset |
|---|---|---|
| 0 | SmartHeat | heat / smart |
| 1 | SmartCool | cool / smart |
| 2 | SmartAuto | auto / smart |
| 3 | BoostHeat | heat / boost |
| 4 | SilenceHeat | heat / silence |
| 5 | BoostCool | cool / boost |
| 6 | SilenceCool | cool / silence |

Other device types (chlorinators, Blue Connect, iQBridge, …) use other component ids; they
are unmapped until diagnostics from their owners arrive.

## 5. Transport of the `amt` heat pump

```
heat pump (ESP32 Wi-Fi) ── MQTT / AWS IoT ──► Fluidra cloud ──► REST + WebSocket ──► Home Assistant
```

- The cloud device record has **no** `commandAndControl.localUdp` for `amt` (that is an
  iQBridge RS feature, see below).
- LAN scans found no open TCP port, no reply to UDP probes (incl. 9003/8902), no SSDP and no
  BLE advertisement in normal operation.
- BLE SPP is used for provisioning (`info.configuration.capabilities.provisioning.ble`):
  service `4e7763c4-211b-47b8-88df-cd869df32c48`, RX `54c4dfef-4e04-4c42-9c33-06a6af86280c`,
  TX `760f6551-4156-4829-8bcc-62591b1eb948`; the app has `SPP8`/`SPP32`/`SPP8X` framing.
- Whether the app ever talks to the pump on the LAN is being checked with an access-point
  packet capture: [docs/LOCAL_CAPTURE.md](docs/LOCAL_CAPTURE.md).

## 6. App internals — hypothesis (from `libapp.so`)

The app is Flutter/Dart; the protocol lives in the AOT snapshot. Packages: `generic_api`
(OpenAPI REST models), `fluidra_iot_generic_api_client`, `fluidra_ble` (iQBridge RS, Lumi+,
Rio, Nodon), `iaqualink_plus` (app).

The cloud chooses the command channel per device (`MobileCommandAndControl`): `…Cloud`
(WebSocket relay), `…LocalUdp` (LAN UDP to an iQBridge RS) or `…Ble` (iQBridge RS).

**Local UDP (iQBridge RS only)** — not implemented:

- Endpoint from `commandAndControl.localUdp` (host, port, token). Port candidates from
  strings: 9003 (most likely), 8902, 9090, 9298, 5781, 5750, 1800, 1801, 3317, 3844.
- Packet: `[0x12 0x34][protocol:1][commandId:2 BE][payloadLen:4 BE][payload][CRC32:4][HMAC-SHA256:32]`.
  Related symbols: `initUdpDeviceListener`, `sendUDPCommand`, `udpKey`, `updateUPDkey`,
  `generateWorkingKey`, `FluidraMessageProtocol`, `getCrc32Byte`, `hmac256`.
- Key: `HMAC-SHA256(key="fluidra", msg=serial)` was guessed; `generateWorkingKey` and
  `updateUPDkey` suggest a refreshable key instead.

**iQBridge ZB**: Zigbee managed with AT commands sent through the cloud (`getZigbeeStatus`,
`setZigbeeStatus`, `getZigbeeInstallCode`, `getZigbeeAddress`, `getAtCommandConfiguration`,
`get/setDefaultRelayStatusInZigbeeMode`).

**BLE (iQBridge RS)**: custom GATT (`base_uuid.dart`), `BleCommandAndControlMessageProtocol`,
`BleAccessCode` for pairing, OTA via MCUmgr, SPP transport.

**Bundled firmware**: `assets/flutter_assets/assets/firmwares/nodon/relay2in1/v4_7_0.gbl`,
a Silicon Labs Zigbee image for the Nodon SR-2-2-0N relay, not iQBridge firmware
([docs/FIRMWARE.md](docs/FIRMWARE.md)).

Worth reading next in the app: `iaqualink_plus/src/tools/devbar/udp_service/udp_devbar.dart`,
`…/devbar/websocket_service/web_socket_devbar.dart`,
`fluidra_flutter_core/src/application/services/websocket/websocket_service.dart`,
`fluidra_ble/src/blue_connect_v3/model.dart`.
