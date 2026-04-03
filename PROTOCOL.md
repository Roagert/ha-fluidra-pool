# Fluidra iQBridge Protocol — Reverse Engineering Findings

> Extracted from `com.fluidra.iaqualinkplus` (XAPK) via `libapp.so` (Flutter/Dart snapshot) analysis.
> Analysis date: 2026-03-29

---

## App Architecture

The official Fluidra Pool app is a **Flutter/Dart** app. All protocol logic lives in
`libapp.so` (the Dart AOT snapshot), not in the Java layer. Key Dart packages:

| Package | Role |
|---------|------|
| `generic_api` | OpenAPI-generated REST client models |
| `fluidra_iot_generic_api_client` | IoT API client (Dart) |
| `fluidra_ble` | BLE transport layer (iQBridge RS, Lumi+, Rio, Nodon) |
| `iaqualink_plus` | Main app (screens, cubits, command & control) |

---

## Command & Control Modes

The app supports **three** distinct command and control channels, selected by the cloud API
(via `MobileCommandAndControl` discriminated union):

| Class | Source file | Description |
|-------|-------------|-------------|
| `MobileCommandAndControlCloud` | `mobile_command_and_control_cloud.dart` | Cloud WebSocket relay |
| `MobileCommandAndControlLocalUdp` | `mobile_command_and_control_local_udp.dart` | **Direct LAN UDP to iQBridge** |
| `MobileCommandAndControlBle` | `mobile_command_and_control_ble.dart` | Bluetooth LE (iQBridge RS) |

The `MobileCommandAndControlLocalUdp` model is the key target for local-first HA integration.

---

## Cloud WebSocket Protocol

### WebSocket Endpoints

| Environment | URL |
|-------------|-----|
| Production  | `wss://ws.fluidra-emea.com` |
| Test        | `wss://test.ws.fluidra-emea.com` |
| Stage       | `wss://stage.ws.fluidra-emea.com` |
| Dev         | `wss://dev.ws.fluidra-emea.com` |

**Authentication:** Bearer token (AWS Cognito JWT — same token as REST API).

### Subscribe to device events

```json
{"action": "subsDevice", "deviceType": "connected", "deviceId": "<device_id>"}
```

### Send a command

```json
{"action": "command", "commandId": "<component_id>", "desiredValue": <value>}
```

### Real-time event model

Class: `WebSocketEvent` (from `WebSocketEventProcessor` / `WebSocketSubscriptionResponseEvent`).

The WebSocket replaces cloud polling with push events — latency drops from 15 min to < 1 s.

### Scheduler WebSocket

There is a separate scheduler WebSocket path. From app source:
- `disableSchedulerWebsockets` flag — the app can disable scheduler WS independently.

---

## Local UDP Protocol (iQBridge RS)

Source: `package:generic_api/src/model/mobile_command_and_control_local_udp.dart`

The `MobileCommandAndControlLocalUdp` model is returned by the cloud API for devices that
support local LAN control (iQBridge RS with local mode enabled). Fields observed from binary:

- `localUdp` — the local UDP configuration object
- Contains: host/IP, port, and authentication token (serial-based key)

**Likely port**: **9003** (best guess from binary strings; candidates: 8902, 9090, 9298, 5781)
**Discovery**: cloud API `commandAndControl.localUdp` field in device response.

### Packet Format (Hypothesis — from Cipher RE session 2026-03-29)

```
[0x12 0x34] [Protocol:1] [CommandID:2 BE] [PayloadLen:4 BE] [Payload:N] [CRC32:4] [HMAC-SHA256:32]
```

Key functions in binary: `initUdpDeviceListener`, `sendUDPCommand`, `udpKey`, `updateUPDkey`,
`FluidraMessageProtocol`, `MagicNumber`, `payloadIntBE`, `payloadIntLE`, `getCrc32Byte`, `hmac256`

### Auth Token Derivation (Hypothesis)

```python
import hmac, hashlib
token = hmac.new(b"fluidra", serial.encode(), hashlib.sha256).hexdigest()
```

> See `PROTOCOL_FINDINGS.md` for full Cipher analysis, extended component map, security findings,
> and verification steps.

---

## REST API

### Base URL
```
https://api.fluidra-emea.com
```

### Key Endpoints (confirmed working)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/generic/users/me` | User profile |
| GET | `/generic/users/me/pools` | User's pools |
| GET | `/generic/pools/{pool_id}/status` | Pool status |
| GET | `/generic/devices/{device_id}/components?deviceType=connected` | All component values |
| GET | `/generic/devices/{device_id}/uiconfig?appId=iaq&deviceType=connected` | UI config (component map) |
| PUT | `/generic/devices/{device_id}/components/{component_id}?deviceType=connected` | Set component value |

### Set Component Value Payload

```json
{"desiredValue": <number>}
```

---

## Component IDs (Heat Pump)

| ID | Name | Unit | Notes |
|----|------|------|-------|
| 13 | Power | 0/1 | 0=off, 1=on |
| 14 | Mode | enum | See modes table below |
| 15 | Set temperature | × 0.1 °C | e.g. 280 = 28.0°C |
| 19 | Water temperature | × 0.1 °C | Read-only sensor |
| 137 | (unknown read sensor) | — | From UI JSON |
| 185 | (unknown read sensor) | — | From UI JSON |
| 272 | (unknown read) | — | componentRead=272 in UI config |
| 276 | (unknown write) | — | componentWrite=276 in UI config |

### Mode Values (Component 14)

| Value | Mode |
|-------|------|
| 0 | Off |
| 1 | Heat |
| 2 | Smart Auto (auto heat/cool) |
| 3 | Manual Heating |
| 4 | Cool |
| 5 | Auto |
| 6 | Night |

---

## iQBridge ZB — Zigbee AT Commands

Source: `package:iaqualink_plus/src/utils/iq_bridge_zb_at_command_codes.dart`

The iQBridge ZB uses AT commands for Zigbee management. Commands observed:

| Command | Description |
|---------|-------------|
| `getZigbeeStatus` | Get Zigbee adapter status |
| `setZigbeeStatus` | Enable/disable Zigbee |
| `getZigbeeInstallCode` | Get Zigbee install code for pairing |
| `getZigbeeAddress` | Get Zigbee MAC address |
| `getAtCommandConfiguration` | Get AT command config |
| `getDefaultRelayStatusInZigbeeMode` | Get relay default state |
| `setDefaultRelayStatusInZigbeeMode` | Set relay default state |
| `formatZigbeeInstallCode` | Format install code for display |

AT commands are sent via the cloud bridge (not directly via BLE on ZB model).

---

## iQBridge RS — BLE Protocol

Source: `package:fluidra_ble/src/blue_connect_v3/`

- BLE transport using custom GATT characteristics (`base_uuid.dart`)
- `BleCommandAndControlMessageProtocol` / `BleConnectMessageProtocol`
- `BleAccessCode` — access code for pairing (shown in iQBridge app)
- OTA update via Silicon Labs MCUmgr (`mcumgr.dart`)
- SPP transport also supported (`spp_transport.dart`)

---

## Bundled Firmware

A **Nodon relay** firmware is bundled in the APK assets:

```
assets/flutter_assets/assets/firmwares/nodon/relay2in1/v4_7_0.gbl
```

This is a **Silicon Labs Zigbee GBL firmware** for Nodon SR-2-2-0N (2-channel in-wall relay).
Not the iQBridge firmware — the iQBridge firmware is delivered via OTA from the cloud.

---

## Authentication

**AWS Cognito** (standard SRP flow):

| Parameter | Value |
|-----------|-------|
| Region | `eu-west-1` |
| User Pool ID | `eu-west-1_OnopMZF9X` |
| Client ID | `g3njunelkcbtefosqm9bdhhq1` |
| Flow | USER_SRP_AUTH → RESPOND_TO_AUTH_CHALLENGE |

Token is a standard JWT Bearer token used for both REST and WebSocket.

---

## Implementation Priority for HA Integration

1. **WebSocket real-time updates** — replace cloud polling with `wss://ws.fluidra-emea.com`
   - Subscribe on connect: `{"action": "subsDevice", "deviceType": "connected", "deviceId": "..."}`
   - Push events update coordinator immediately
   - Target latency: < 2 s (vs 15 min polling)

2. **Local UDP** — direct LAN access (eliminates cloud dependency)
   - Requires: iQBridge RS device + capture of `MobileCommandAndControlLocalUdp` payload from cloud API
   - The cloud API returns the local UDP endpoint when iQBridge is on same LAN

3. **BLE** — direct Bluetooth (no network required, mobile-only)

---

## Files to Investigate Further

| File | Purpose |
|------|---------|
| `package:iaqualink_plus/src/tools/devbar/udp_service/udp_devbar.dart` | Dev tool for UDP — may reveal port/format |
| `package:iaqualink_plus/src/tools/devbar/websocket_service/web_socket_devbar.dart` | Dev tool for WS — reveals message structure |
| `package:fluidra_flutter_core/src/application/services/websocket/websocket_service.dart` | WS service implementation |
| `package:fluidra_ble/src/blue_connect_v3/model.dart` | BLE command model |
