# Firmware Analysis: Nodon SIN-2-in-1 v4.7.0 (EFR32)
**Date:** 2026-03-30 | **Source:** APK `com.fluidra.iaqualinkplus` bundled asset
**File:** `assets/firmwares/nodon/relay2in1/v4_7_0.gbl`

---

## Binary Metadata

| Field | Value |
|-------|-------|
| File format | GBL (Silicon Labs Gecko Bootloader) |
| Outer wrapper | `0x0BEEF11E` magic — Fluidra OTA container |
| Inner GBL start offset | 0x3E |
| Total file size | 392,032 bytes (382.8 KB) |
| Product ID string | `fluidra_sin_efr32_ota` |
| Firmware ID | `p1833_fluidra_sin_2_fw_efr32` |
| Firmware version | v4.7.0 |
| Target CPU | Silicon Labs **EFR32** (EFR32MG series, multi-protocol: Zigbee + BLE) |
| Second CPU | **STM32** (host MCU, communicates with EFR32 via UART serial) |
| Architecture | ARM Cortex-M33 (EFR32xG21+) |

---

## GBL Tag Structure

| Offset | Tag ID | Tag Name | Size |
|--------|--------|----------|------|
| 0x003E | 0x03A617EB | GBL_HEADER_V3 | 8 B |
| 0x004E | 0xF40A0AF4 | GBL_BOOTLOADER_UPGRADE | 28 B |
| 0x0072 | 0xF50909F5 | Program data block 1 | 10,096 B |
| 0x27EA | 0xFD0303FD | Program data block 2 (main app) | 381,700 B |
| 0x5FB3E | 0xFC0404FC | End tag + CRC | 4 B (CRC=0xC00A3494) |

---

## Security Analysis

| Property | Value |
|----------|-------|
| ECDSA-P256 signature | **ABSENT — FIRMWARE IS UNSIGNED** |
| Encryption | **NONE — FIRMWARE IS PLAINTEXT** |
| Signature tag 0xF50B01B6 | Not found |
| Certificate tag 0xF30B01B6 | Not found |

### Critical Implication
**Custom firmware can be flashed via BLE OTA without bypassing any signature check.**
The `flutter_reactive_ble` OTA transport (`FlutterReactiveBleOtaTransport`) in the Fluidra app
uses the Silicon Labs DFU service (`1d14d6ee-fd63-4fa1-bfa4-8f47b42119f0`) to push GBL files.
Since there is no ECDSA signature verification, any valid GBL file can be accepted.

---

## Hardware Architecture

```
┌──────────────────────────────────────────────────────┐
│  Nodon SIN-2-in-1 (iQBridge ZB)                     │
│                                                      │
│  ┌─────────────┐   UART serial   ┌───────────────┐  │
│  │    STM32    │◄───────────────►│   EFR32MG     │  │
│  │  (host MCU) │   [SERIAL]      │  (radio MCU)  │  │
│  │  relays,    │   protocol      │  Zigbee + BLE │  │
│  │  scheduler, │                 │  stack        │  │
│  │  buttons    │                 │               │  │
│  └─────────────┘                 └───────────────┘  │
│                                        │            │
│                               BLE + Zigbee antenna  │
└──────────────────────────────────────────────────────┘
```

### STM32 Serial Protocol (`[SERIAL]` messages)
- Framed protocol with CRC verification
- Duplicate packet detection (sequence numbers)
- Pool-based TX/RX buffer management
- Error handling: bad CRC, bad ack, frame size errors

---

## BLE Command Interface

All commands require `CMD_SET_ACCESS_CODE` before execution (access code gating).

### Authentication
| Signal | Meaning |
|--------|---------|
| `[BLE]: Set access code first.` | Access code required before any command |
| `[BLE]: Auth timeout` | Auth session expires |
| `[BLE]: Bad CRC in received frame.` | Frame integrity check |
| `[BLE]: Bad seed in received frame.` | Nonce/seed mismatch (replay protection) |

### Full BLE Command Set
| Command | Description |
|---------|-------------|
| `CMD_FACTORY_RESET` | Full factory reset |
| `CMD_GET_DEVICE_TYPE` | Read device type |
| `CMD_GET_FW_VERSION` | Read EFR32 firmware version |
| `CMD_GET_HW_VERSION` | Read hardware version (antenna + power PCBAs) |
| `CMD_SET_HW_POWER_PCBA` | Set power PCBA version |
| `CMD_SET_HW_ANTENNA_PCBA` | Set antenna PCBA version |
| `CMD_GET_SN` | **Read serial number** |
| `CMD_GET_BLE_ADDRESS` | Read BLE MAC address |
| `CMD_GET_ZB_ADDRESS` | Read Zigbee EUI-64 address |
| `CMD_GET_MODE` / `CMD_SET_MODE` | Get/set operating mode (scheduler/zigbee/manual) |
| `CMD_GET_RTC` / `CMD_SET_RTC` | Get/set real-time clock |
| `CMD_SET_ACCESS_CODE` / `CMD_GET_ACCESS_CODE` | Manage BLE access code |
| `CMD_GET_SCHEDULER_CONF` / `CMD_SET_SCHEDULER_CONF` | Read/write schedule slots |
| `CMD_REMOVE_SCHEDULER_CONF` / `CMD_REMOVEALL_SCHEDULER_CONF` | Delete schedule(s) |
| `CMD_GET_ZB_STATUS` / `CMD_SET_ZB_STATUS` | Zigbee network status |
| `CMD_GET_DEFAULT_RELAY_STATUS_ZB_MODE` / `CMD_SET_...` | Default relay state in Zigbee mode |
| `CMD_GET_ZIGBEE_INSTALL_CODE` | **Read Zigbee install code** |
| `CMD_GET_RELAY_STATUS` / `CMD_SET_RELAY_STATUS` | Read/write relay state |
| `CMD_GET_FRONT_BUTTON_STATUS` | Read physical button state |

### Operating Modes
```
scheduler mode  — automatic timer-based relay control
zigbee mode     — controlled by Zigbee coordinator (iQBridge RS / gateway)
Manual OFF      — relay forced off
Manual ON       — relay forced on
```

---

## Zigbee Stack Details

| Property | Value |
|----------|-------|
| Stack | EmberZNet (Silicon Labs) |
| TC link key | `ZigBeeAlliance09` (default well-known key) |
| Join modes | Install Code, Centralized key, Distributed key |
| OTA over Zigbee | `ota-storage-eeprom.c` present → EEPROM-backed OTA |
| Safe mode | Activates if gateway connection lost (configurable timeout) |

### Zigbee Security
- Default TC link key `ZigBeeAlliance09` is the **well-known** Zigbee standard key
- Install code joining also supported (`CMD_GET_ZIGBEE_INSTALL_CODE`)
- A device using the default well-known key can be joined by any Zigbee sniffer

---

## STM32 Host MCU

Referenced as a separate MCU communicating over serial:
```
STM32 Version %d.%d.%d
```
The EFR32 receives commands via BLE → relays them to STM32 over serial.
STM32 likely controls:
- The actual relay outputs
- Front panel button/LED
- Power management
- Color/LED strip control (`[COLOR]`)

---

## Key Firmware Strings

```
p1833_fluidra_sin_2_fw_efr32    ← product/SKU identifier
SIN-4-2-20                       ← hardware variant code
fluidra_sin_efr32_ota            ← OTA product identifier in GBL wrapper
[ZB]: Connection to GW lost, safe mode activation in %d min.
[ZB]: EUI64:                     ← Zigbee extended address logged
[UTIL]: S/N:                     ← serial number logged
[UTIL]: Install Code:            ← Zigbee install code logged to UART
[UTIL]: BLE MAC:                 ← BLE MAC logged to UART
[BLE]: Bad seed in received frame. ← replay protection on BLE frames
```

---

## OTA Update Flow

```
Android app (flutter_reactive_ble)
        │
        │  Silicon Labs DFU Service (1d14d6ee...)
        │  GBL file streamed in chunks
        ▼
EFR32 Bootloader (no signature verification)
        │
        │  Flash write
        ▼
New EFR32 firmware running
```

**Attack surface:** No GBL signature check → write custom GBL → flash arbitrary firmware.
Custom firmware could expose:
- Direct relay control via MQTT/REST
- Full Zigbee sniffing mode
- Remove access code requirement
- ESPHome-style local API

---

## Custom Firmware Plan

Based on hardware:
- **EFR32MG series** → use Silicon Labs **Simplicity Studio** + **Gecko SDK**
- Alternative: **OpenThread/Z-Stack** port if supported
- The STM32 serial protocol must be reverse engineered for relay control
- **ESPHome for EFR32** does not exist — need custom Gecko SDK app

### Minimal Custom Firmware Goals
1. Remove access code requirement
2. Expose relay control via Zigbee (to HA ZHA integration directly)
3. Keep BLE for pairing/commissioning
4. Add UART debug output for STM32 protocol capture

### Flashing Method
1. Connect Android device with BLE to Nodon device
2. Use `flutter_reactive_ble` compatible BLE client OR nRF Connect app
3. Navigate to Silicon Labs DFU service (UUID `1d14d6ee-...`)
4. Upload custom GBL → no signature check → flashes immediately

---

## Task Implications

| Task | Finding |
|------|---------|
| FW-001 (OTA URL) | Firmware is bundled in APK — no separate download URL needed |
| FW-002 (Binary analysis) | DONE — full string extraction, hardware ID, BLE command set |
| FW-003 (Custom firmware) | Unsigned GBL = flashable; EFR32 → Gecko SDK; STM32 serial RE needed |
| TASK-002 (Local UDP) | Not directly related — iQBridge RS is separate hardware |
| Security | TC link key is default `ZigBeeAlliance09` → Zigbee network joinable without install code |
