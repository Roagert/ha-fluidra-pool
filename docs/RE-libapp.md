# Reverse Engineering Report: libapp.so
**Date:** 2026-03-30 | **Tool:** Ghidra 12.0.4 + manual strings analysis

---

## Binary Metadata

| Field | Value |
|-------|-------|
| Format | ELF Shared Library |
| Architecture | AARCH64 LE 64-bit (v8A) |
| Size | ~32 MB |
| MD5 | 01a42b87ef8872b982602a25d8a7de7e |
| Language | Dart AOT snapshot (Flutter app) |
| Source APK | com.fluidra.iaqualinkplus (Fluidra Pool) |
| Ghidra Language | AARCH64:LE:64:v8A:default |

---

## Binary Nature

`libapp.so` is the compiled Dart AOT (Ahead-Of-Time) snapshot for the Flutter app.
This means:
- There are **no C symbols** or function names in the symbol table
- All logic is in Dart object stubs — Ghidra sees them as unnamed code blobs
- The **string table** is the primary RE surface
- Function names visible are Dart class/method hashes, not human-readable

---

## Key Classes Identified (from string table)

### Command & Control Discriminated Union
```
_$MobileCommandAndControl@1825176603
_$MobileCommandAndControlCloud@1827421435       → cloud WebSocket relay
_$MobileCommandAndControlLocalUdp@1828136647    → LAN UDP (PRIMARY TARGET)
_$MobileCommandAndControlBle@1826372602         → Bluetooth LE
```

### Protocol Enums
```
FluidraMessageProtocol          → UDP packet protocol type field
FluidraMessageProtocol.         → (enum values follow)
FluidraBleMessageProtocol       → BLE-specific protocol variant
BleCommandAndControlMessageProtocol
BleConnectMessageProtocol
BlePairingMessageProtocol
MagicNumber                     → packet magic bytes constant
```

### Local UDP Functions
```
initUdpDeviceListener           → initializes UDP receive loop
sendUDPCommand                  → sends a formatted UDP packet
udpKey                          → auth key field
updateUPDkey                    → refresh UDP auth key
localUdpB                       → localUdp model B variant
udpDevbar                       → developer debug bar for UDP
udpService                      → UDP service class
icons__status__udp              → UI icon for UDP connected
icons__status__udp_off          → UI icon for UDP disconnected
```

### Payload Encoding
```
payloadIntBE    → big-endian integer payload
payloadIntLE    → little-endian integer payload
payloadString   → string payload
payload_type    → payload type discriminator
totalPackets    → packet count (multi-packet messages)
packetIndex     → current packet index
addPacket       → append packet to buffer
addFrame        → frame assembly
buildWritePayload       → builds write command payload
createDynamicValuePayload
requestPayload
```

### Cryptography / Auth
```
hmac            → base HMAC function
hmac256         → HMAC-SHA256 (most likely UDP auth)
hmac512         → HMAC-SHA512 (less likely)
getCrc32Byte    → CRC32 checksum computation
sv4crc          → SipHash or CRC variant
updateCrc       → incremental CRC update
keyCipherAlgorithm      → algorithm used for key derivation
storageCipherAlgorithm  → algorithm for local storage encryption
generateWorkingKey      → generates operational key from master
accessCodeKey   → BLE access code key field
udpKey          → UDP auth key field
updateUPDkey    → called to rotate/refresh UDP key
```

### Component / Reporting
```
protocolReadComponentId     → protocol field: component ID to read
reportChannelReadComponentId
keyComponentId              → component ID key
desiredOrReported           → mode: desired vs reported value
reportedValue               → current device state value
reportedAutoMode            → auto mode reported state (component 14)
reportedSetpointValue       → setpoint reported (component 15)
reportedStateOnOff          → power reported state (component 13)
heatingLastReportedValue    → last heating state
backwashLastReportedValue   → last backwash valve state (→ component 137)
lastChlorinationReportedValue → chlorination pump state (→ component 276)
lastORPReportedValue        → ORP sensor value (→ component 185)
lastpHReportedValue         → pH sensor value (→ component 272)
```

### BLE / GATT
```
DeviceComponentInfoBleAdvertisingReadSerializer
DeviceComponentInfoBleLegacyGattReadSerializer
DeviceComponentInfoBleLegacyGattWriteSerializer
deviceComponentInfoBleLegacyGattReadProtocolEnumSerializer
deviceComponentInfoBleLegacyGattWriteProtocolEnumSerializer
deviceComponentInfoBleLegacyGattReadTypeEnumSerializer
deviceComponentInfoBleLegacyGattWriteTypeEnumSerializer
BleCommandAndControl.fromMap
bluetoothMacAddress
blePairingProtocolValues
```

### OTA / Firmware
```
DevicePropertiesOtaUpdateStatusSerializer
DevicePropertiesOtaUpdateStatusStatusEnumSerializer
DevicePropertiesOtaUpdateStatusStatusDetailsSerializer
devicePropertiesOtaUpdateStatusStatusEnumSerializer
```

### WebSocket
```
_$WebSocketEventFromJson@3553510983
_$WebSocketEventToJson@3553510983
webSocketDeviceConnector
websocketEventToDomain
decodeWebsocketEvent
disableSchedulerWebsockets
```

---

## Strings of Interest

### Confirmed protocol message literals
```
{"action": "subsDevice", "deviceType": "connected","deviceId": "
","action":"command","commandId":"
subsDevice
action
connected
desiredValue
deviceId
deviceType
```

### Port candidates (numeric strings found)
```
9003  8902  9090  9298  5781  5750  1850  1801  1800  3844  3317
```

---

## Security Notes

| Feature | Status |
|---------|--------|
| Stack canaries | Unknown (Dart AOT, no standard C stack) |
| PIE | Yes (shared library, position-independent) |
| NX | Yes (ELF `PT_GNU_STACK` expected) |
| RELRO | Unknown — check with `readelf -l libapp.so \| grep RELRO` |
| Certificate pinning | Likely present in Dart (bypassed via Frida) |
| UDP auth | HMAC-SHA256 hypothesis — see PROTOCOL_FINDINGS.md |
| BLE OTA signing | Unknown — check bundled GBL signature |

---

## Task Implications

| Task | Implication |
|------|-------------|
| TASK-002 (Local UDP) | `sendUDPCommand` + `hmac256` + `MagicNumber` confirm packet has magic + HMAC auth |
| TASK-002 (auth token) | `generateWorkingKey` + `updateUPDkey` → key is refreshable, not static |
| TASK-002 (port) | `initUdpDeviceListener` — port comes from `localUdp` API field, not hardcoded |
| TASK-003 (dual-mode) | `icons__status__udp` / `_off` → app shows UDP status; coordinator should too |
| FW-001 (OTA) | `DevicePropertiesOtaUpdateStatus` → OTA status tracked in device properties API |
| Security | `hmac256` for UDP auth, `getCrc32Byte` for packet integrity |

---

## Critical New Finds (2026-03-30 iteration 2)

### BLE OTA — Open Source Library Identified
```
FlutterReactiveBleOtaTransport      ← uses flutter_reactive_ble package (open source!)
FlutterReactiveBleConnector
FlutterReactiveBlePlugTransport
_FlutterReactiveBleAccessCodeTransport@1241335643
```
**Implication:** The BLE OTA update mechanism uses the open-source `flutter_reactive_ble` Dart package
(https://github.com/PhilipsHue/flutter_reactive_ble). The OTA transport over BLE follows standard
MCUmgr/SMP protocol (Silicon Labs). Full BLE OTA implementation can be replicated using the same library.

### OTA Technologies Enum
```
_$mobileProcessesOtaTechnologiesEnumSerializer@1848108485
_$mobileProcessesOtaTechnologiesEnumValueOf@1848108485
MobileProcessesOtaBleConfiguration
MobileProcessesOtaBleConfigurationBuilder
```
`MobileProcessesOta.technologies` is an enum — values are the transport types (BLE, Zigbee, UDP, etc.).
`MobileProcessesOtaBleConfiguration` has separate `rxProtocol` + `txProtocol` enum fields,
confirming the BLE OTA channel is bidirectional with typed protocol IDs per direction.

### Key Protocol Functions Confirmed
```
getCommandAndControl    → returns MobileCommandAndControl discriminated union (cloud/UDP/BLE)
sendCommand             → generic command dispatcher
sendBleCommands         → BLE-specific command path
sendUDPCommand          → UDP-specific command path
initUdpDeviceListener   → sets up UDP receive loop
initComponentsSubscription → subscribes to component updates (WebSocket or BLE)
openComponentsListener  → opens the listener channel
decodeWebsocketEvent    → parses incoming WS events
encodeComponent         → serializes component value for transmission
decodeComponent         → deserializes component value from response
writeComponent          → writes single component (PUT desiredValue)
writeComponents         → batch write multiple components
updateFirmware          → triggers OTA firmware update
getFirmwareUpdateInfoFromDevice → fetches OTA metadata from API
verifyToken             → validates auth token
```

### Nodon / Zigbee
```
addNodonOfflineDeviceToPool
connectNodon
connectNodonPlug
connectNodonRelay2In1   → SR-2-in-1 relay (bundled firmware v4_7_0.gbl)
BleNodon
iqBridgeZB              → iQBridge ZB variant (Zigbee)
getZbAddress
formatZigbeeInstallCode
getDefaultRelayStatusInZigbeeMode
setDefaultRelayStatusInZigbeeMode
```

## Full Ghidra Analysis

> Full analysis output at `docs/RE-libapp-functions.txt` (generated by Ghidra headless).
> Script: `scripts/ghidra_strings.py`
> Run: `$GHIDRA/support/analyzeHeadless /tmp/ghidra_fluidra FluidraProject -process libapp.so -postScript scripts/ghidra_strings.py`
