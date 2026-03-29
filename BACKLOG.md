# Fluidra Pool — Backlog

> See PROTOCOL.md for full reverse-engineering findings.

---

## P1 — Local-First Integration (Primary Goal)

### LOCAL-001 — WebSocket Real-Time Updates
**Status:** Ready to implement
**Why:** Cloud polling every 15 min gives terrible UX. The app uses `wss://ws.fluidra-emea.com` for real-time push events. Replacing polling with WebSocket reduces response time from 15 min → < 2 s.

**Approach:**
1. On coordinator start, open a WebSocket to `wss://ws.fluidra-emea.com` with Bearer token
2. Send subscribe message: `{"action": "subsDevice", "deviceType": "connected", "deviceId": "<id>"}`
3. Push `WebSocketEvent` to coordinator on each message
4. Keep cloud polling as fallback (every 15 min as health check)

**Files:** `coordinator.py`, `const.py`

---

### LOCAL-002 — Local UDP Client (iQBridge RS)
**Status:** Research phase
**Why:** Eliminates all cloud dependency. Commands execute in < 100 ms. Works when internet is down.

**Approach:**
1. After auth, call `/generic/devices/{id}?deviceType=connected` — check for `commandAndControl.localUdp` field
2. If present, extract `host`, `port`, `token` from `MobileCommandAndControlLocalUdp`
3. Implement UDP socket client using the extracted protocol
4. Use as primary path when on same LAN as iQBridge; fall back to cloud/WS

**Blocker:** Need to capture the `commandAndControl` field from live API response. Enable debug logging to see full device JSON, then extract `localUdp` object.

**Files:** `local_client.py` (new), `coordinator.py`, `config_flow.py`

---

### LOCAL-003 — Dual-Mode Coordinator
**Status:** Depends on LOCAL-002
**Why:** Seamless fallback between local → WS → cloud polling

**Config flow addition:** `connection_mode` selector: `auto` / `cloud_only` / `local_only`

**Files:** `coordinator.py`, `config_flow.py`

---

## P2 — Bug Fixes

### BUG-001 — Smart Auto mode shows as "heat" or "cool" instead of "auto"
**Status:** Ready to fix
**Symptom:** When heat pump is in Smart Auto mode (component 14 = 2), HA climate card shows "heat" or "cool" based on temperature comparison, not "auto". User cannot distinguish Smart Auto from forced heating/cooling.

**Fix:**
- Add `HVACMode.AUTO` to `_attr_hvac_modes`
- Return `HVACMode.AUTO` when `preset_mode == "Smart Auto"` (component 14 value 2)
- Keep temperature-based logic for `hvac_action` (heating/cooling) only
- Setting `hvac_mode = "auto"` should activate Smart Auto (component 14 = 2)

**File:** `custom_components/fluidra_pool/climate.py`

---

### BUG-002 — Remove deprecated FluidraConsumerSensor entity
**Status:** Ready to fix
**Symptom:** `FluidraConsumerSensor` uses the deprecated `/mobile/consumers/me` endpoint. This endpoint is being superseded by `/generic/users/me` (already implemented as `FluidraUserProfileSensor`). Creates duplicate data + may break when Fluidra removes the old endpoint.

**Fix:** Remove `FluidraConsumerSensor` class and its setup in `async_setup_entry`.

**File:** `custom_components/fluidra_pool/sensor.py`

---

### BUG-003 — Diagnostic sensor values missing from attributes
**Symptom:** Some diagnostic sensors return state `None` or `unknown` but have data.
**Fix:** Ensure `FluidraErrorSensor` properly surfaces error code + human-readable message together.

**File:** `custom_components/fluidra_pool/sensor.py`

---

## P3 — New Features

### FEAT-001 — Salt Chlorinator Sensors
**Status:** Ready to implement
**Why:** Chlorinator component data is available via the components API but not exposed as HA entities. Users want pH, ORP, salinity, and free chlorine as real sensors.

**New sensor entities:**
| Entity | Component | Unit | HA device class |
|--------|-----------|------|-----------------|
| pH | (from uiconfig) | pH | none |
| ORP | (from uiconfig) | mV | voltage |
| Salinity | (from uiconfig) | g/L | none |
| Free Chlorine | (from uiconfig) | ppm | none |

**Approach:** Parse `device_uiconfig_data` for component IDs matching `ph_key`, `orp_key`, `salinity_key`, `free_chlorine_key` i18n keys. Create sensor entities dynamically.

**File:** `custom_components/fluidra_pool/sensor.py`

---

### FEAT-002 — Water temperature sensor (standalone)
**Status:** Easy win — component 19 already read by coordinator
**Why:** Current water temperature is only exposed via climate entity's `current_temperature`. Should also be a standalone `sensor` entity so it appears in HA history graphs.

**File:** `custom_components/fluidra_pool/sensor.py`

---

### FEAT-003 — MQTT bridge
**Status:** Backlog
**Why:** Publish pool state to local MQTT broker so automations can react without HA polling.

**Topics:**
```
fluidra_pool/<device_id>/power → 0/1
fluidra_pool/<device_id>/mode → 0-6
fluidra_pool/<device_id>/water_temp → °C
fluidra_pool/<device_id>/set_temp → °C
```

**File:** `mqtt_bridge.py` (new)

---

## P4 — Firmware Reverse Engineering

### FW-001 — Identify iQBridge firmware delivery mechanism
**Status:** Research
**Approach:** Capture network traffic during iQBridge firmware update. Look for OTA URL pattern in Fluidra app decompiled source (Dart function `mobileProcessesOtaBleConfiguration` / `DevicePropertiesOtaUpdateStatus`).

### FW-002 — Extract iQBridge RS firmware binary
**Status:** Depends on FW-001
**Tools:** binwalk, strings, Ghidra

### FW-003 — Custom firmware design
**Status:** Depends on FW-002
**Target:** ESP32 or Nordic nRF52 based (unknown until FW-002)
**Output:** `CUSTOM_FIRMWARE.md`

---

## Implementation Order

```
1. BUG-001  (Smart Auto mode) — 30 min
2. BUG-002  (remove deprecated entity) — 10 min
3. FEAT-002 (water temp sensor) — 20 min
4. FEAT-001 (chlorinator sensors) — 1 h
5. LOCAL-001 (WebSocket real-time) — 2-3 h
6. LOCAL-002 (local UDP) — needs live capture first
7. LOCAL-003 (dual-mode coordinator) — depends on LOCAL-002
8. FW-001 → FW-002 → FW-003 (firmware) — long-term
```
