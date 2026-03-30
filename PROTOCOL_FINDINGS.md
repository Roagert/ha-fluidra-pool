# Fluidra Protocol Findings — Live Capture + RE Analysis
**Last updated:** 2026-03-30 | **Status: CONFIRMED** (live API capture + fluidra_debug.py)

---

## Device Inventory

| Field | Value |
|-------|-------|
| Device ID | `LG24440781` |
| Serial (SN) | `LG24440781` |
| Device type | `amt` (Amitime — Swim & Fun Inverter Heat Pump) |
| Thing type | `connected` |
| SKU | `1441` |
| Firmware | `2.5.0` |
| LAN IP | `192.168.1.11` |
| WiFi module SN | `BXWAB0603494724050` |
| WiFi RSSI | `-82 dBm` |
| Pool ID | `6cfd9bc9-09e8-547d-9f5a-0274c170a915` |
| User | `thomasroager@gmail.com` (Thomas Roager, DK) |

---

## Authentication — CONFIRMED

### Cognito User Pool
| Field | Value |
|-------|-------|
| Region | `eu-west-1` |
| User Pool ID | `eu-west-1_OnopMZF9X` |
| Client ID | `g3njunelkcbtefosqm9bdhhq1` |
| Auth flow | `USER_PASSWORD_AUTH` |
| Token TTL | 300 seconds |

```python
import boto3
client = boto3.client("cognito-idp", region_name="eu-west-1")
resp = client.initiate_auth(
    ClientId="g3njunelkcbtefosqm9bdhhq1",
    AuthFlow="USER_PASSWORD_AUTH",
    AuthParameters={"USERNAME": email, "PASSWORD": password},
)
access_token = resp["AuthenticationResult"]["AccessToken"]
```

---

## REST API — CONFIRMED

### Base URLs
| Environment | REST Base |
|-------------|-----------|
| Production | `https://api.fluidra-emea.com` |

### Key Endpoints (all confirmed working)

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

| Method | URL | Purpose |
|--------|-----|---------|
| GET | `/generic/users/me` | User profile |
| GET | `/generic/users/me/pools` | Pool list |
| GET | `/generic/devices?deviceType=connected` | Device list |
| GET | `/generic/devices/{id}?deviceType=connected` | Device detail |
| GET | `/generic/devices/{id}/components?deviceType=connected` | All components |
| GET | `/generic/devices/{id}/components/{cid}?deviceType=connected` | Single component |
| PUT | `/generic/devices/{id}/components/{cid}?deviceType=connected` | Set component value |

### Component GET Response
```json
{
  "id": 13,
  "reportedValue": 0,
  "ts": 1758877765
}
```

### Component PUT Request
```json
{ "desiredValue": 1 }
```

### Component PUT Response
```json
{
  "id": 15,
  "reportedValue": 290,
  "desiredValue": 290,
  "ts": 1758204079
}
```

---

## WebSocket — CONFIRMED

### Connection
```
wss://ws.fluidra-emea.com?token=<access_token>
```
**Note:** Token goes in URL query param, NOT in Authorization header.

### Subscribe message
```json
{
  "action": "subsDevice",
  "deviceType": "connected",
  "deviceId": "LG24440781"
}
```

### Subscribe response
```json
{
  "statusCode": 200,
  "action": "subsDevice",
  "body": "{\"deviceId\":\"LG24440781\",\"deviceType\":\"connected\",\"message\":\"OK\"}"
}
```

### Push notification format (expected when device sends state update)
```json
{
  "action": "command",
  "deviceId": "LG24440781",
  "deviceType": "connected",
  "componentId": "13",
  "reportedValue": 1
}
```

---

## Component Map — CONFIRMED (live capture 2026-03-30)

### System / Identity Components (read-only)

| ID | Type | Value | Meaning |
|----|------|-------|---------|
| 0 | int | 409 | Operational hours counter (÷1) |
| 1 | int | -82 | WiFi RSSI (dBm) |
| 2 | str | `192.168.1.11` | Device LAN IP address |
| 3 | str | `LG24440781` | Device serial number |
| 4 | str | `2.5.0` | Firmware version |
| 5 | str | `amt` | Device model code |
| 6 | str | `1441` | SKU number |
| 7 | str | `BXWAB0603494724050` | WiFi module serial |
| 8 | — | None | Reserved |
| 9 | str | `` | Empty/unused |
| 10 | json | `[{"p":"nn","id":"nn_1"}]` | Connected accessories config |

### Control Components (read/write)

| ID | Type | Value | Meaning | Range |
|----|------|-------|---------|-------|
| 11 | int | 1 | Heat pump active state | 0=idle, 1=running |
| 13 | int | **0** | **POWER** | 0=OFF, 1=ON |
| 14 | int | **2** | **MODE** | 0=SmartHeat, 1=SmartCool, 2=SmartAuto, 3=BoostHeat, 4=SilenceHeat, 5=BoostCool, 6=SilenceCool |
| 15 | int | **290** | **SET TEMPERATURE** (×0.1 °C = **29.0°C**) | 150–420 (15.0–42.0°C) |
| 16 | int | 2 | Target mode / auto sub-mode | TBD |
| 17 | int | 0 | Timer/schedule flag | 0=off |
| 18 | int | 0 | Anti-freeze / silent flag | 0=off |

### Sensor Components (read-only, ×0.1 °C)

| ID | Type | Value | Meaning |
|----|------|-------|---------|
| 19 | int | **131** | **Water temperature** = **13.1°C** |
| 62 | int | 320 | Ambient/outdoor air temp = 32.0°C |
| 65 | int | 138 | Temperature sensor 65 = 13.8°C |
| 66 | int | 149 | Temperature sensor 66 = 14.9°C |
| 67 | int | 199 | Temperature sensor 67 = 19.9°C |
| 68 | int | 131 | Temperature sensor 68 = 13.1°C (water in?) |
| 69 | int | 131 | Temperature sensor 69 = 13.1°C |
| 70 | int | 140 | Temperature sensor 70 = 14.0°C |

**Note:** 83 total components — full list in `fluidra_debug_20260330_132940.json`.

---

## Device Type: `amt` (NOT iQBridge RS)

**Critical finding:** This device is an **Amitime heat pump** with integrated WiFi — NOT an iQBridge RS.

| Property | iQBridge RS | This device (amt) |
|----------|-------------|-------------------|
| Cloud | MQTT via iQBridge | Direct MQTT (AWS IoT) |
| Local UDP | YES — `commandAndControl.localUdp` | NOT PRESENT |
| BLE | NO | YES — SPP provisioning |
| `commandAndControl` | Has `localUdp` field | Not found in API |

### Communication Architecture (amt device)

```
Heat pump (LG24440781)
        │
        │ WiFi → MQTT → AWS IoT
        ▼
Fluidra Cloud (api.fluidra-emea.com)
        │
        ├── REST API (GET/PUT components)
        └── WebSocket (wss://ws.fluidra-emea.com?token=...)
                │
                └── HA Integration (coordinator.py)
```

### Local Control Options (confirmed / hypothetical)
1. **REST PUT** (confirmed) — via cloud API, commands stored even when device offline
2. **WebSocket subscribe** (confirmed) — near-real-time push when device online
3. **Local HTTP** (hypothesis) — port scan of 192.168.1.11 needed from LAN
4. **Local UDP** (hypothesis) — binary strings confirm port 9003 in app; amt may have it
5. **BLE SPP** (confirmed in binary) — serviceUuid `4e7763c4-...`, rxUuid/txUuid confirmed

---

## BLE SPP Service (provisioning + potential control)

Found in device API response under `info.configuration.capabilities.provisioning.ble`:

| Field | UUID |
|-------|------|
| Service UUID | `4e7763c4-211b-47b8-88df-cd869df32c48` |
| RX UUID | `54c4dfef-4e04-4c42-9c33-06a6af86280c` |
| TX UUID | `760f6551-4156-4829-8bcc-62591b1eb948` |
| Protocol | SPP (Bluetooth Serial Port Profile) |

SPP variants in binary: `SPP8`, `SPP32`, `SPP8X` — multi-packet framing protocol.

---

## Local Protocol Discovery — Needed

The device has LAN IP `192.168.1.11`. Port scan from LAN needed to determine if there's a local HTTP/WebSocket/UDP API.

### Recommended scan (run from home LAN)
```bash
# From a machine on 192.168.1.x network:
nmap -sT -sU -p 80,443,8080,8443,502,9003,8902,5781,5750,1800,1801 192.168.1.11
# Or quick:
nmap -F 192.168.1.11
```

### If port 80/8080 responds:
```bash
curl http://192.168.1.11/
curl http://192.168.1.11/api/
curl http://192.168.1.11/status
```

---

## Prior Hypothesis: Local UDP (iQBridge RS)

The earlier UDP hypothesis (`local_client.py`) was based on `commandAndControl.localUdp` field from iQBridge RS devices. This field does NOT appear for `amt` type devices.

UDP port candidates from binary strings (still valid for iQBridge RS devices):
```
9003  8902  5781  5750  1800  1801  3317  3844
```

---

## Live Debug Session (2026-03-30)

### What was confirmed
1. ✅ Cognito auth works: `USER_PASSWORD_AUTH` → `access_token`
2. ✅ REST API: GET/PUT components via `Authorization: Bearer <access_token>`
3. ✅ WebSocket: `wss://ws.fluidra-emea.com?token=<access_token>`
4. ✅ Component 13 = power (0=OFF), 15 = setpoint (290=29.0°C), 19 = water temp (131=13.1°C)
5. ✅ PUT to setpoint returns HTTP 200 with updated desiredValue
6. ✅ 83 components total — full map in JSON output

### What is blocked / needs LAN access
1. ❌ Local UDP / local HTTP — needs LAN scan from 192.168.1.x
2. ❌ WebSocket push — device offline (MQTT_KEEP_ALIVE_TIMEOUT) during session
3. ❌ `commandAndControl.localUdp` — not present for amt devices

### Debug output files
- `fluidra_debug_20260330_132940.json` — raw API dump (83 components)
- `docs/FIRMWARE.md` — Nodon EFR32 firmware analysis

---

## Task Implications Update

| Task | Status | Notes |
|------|--------|-------|
| TASK-002 (local UDP) | REVISED — not applicable for amt | localUdp is for iQBridge RS only |
| TASK-003 (coordinator) | UNBLOCKED | REST PUT + WS confirmed working |
| TASK-004 (RE) | DONE | 83 components mapped |
| TASK-DYN-001 (credentials) | RESOLVED | S0davand! works |
| New: LAN scan | PENDING | Needs run from 192.168.1.x network |
