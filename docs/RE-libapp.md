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

## Critical New Finds (2026-03-30 iterations 2–3)

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

## GATT UUIDs Extracted

### Identified (known assignments)
| UUID | Assignment |
|------|-----------|
| `00002902-0000-1000-8000-00805f9b34fb` | CCCD — standard BLE descriptor |
| `1d14d6ee-fd63-4fa1-bfa4-8f47b42119f0` | **Silicon Labs OTA DFU Service** |
| `984227f3-34fc-4045-a5d0-2c581f81a153` | **Silicon Labs OTA Control Characteristic** |
| `8d53dc1d-1db7-4cd3-868b-8a527460aa84` | Nordic UART Service (NUS) TX |
| `258EAFA5-E914-47DA-95CA-C5AB0DC85B11` | WebSocket RFC 6455 magic (not GATT) |

### Likely Custom Fluidra/iQBridge GATT UUIDs
```
0AD5190E-640D-4E05-9E47-2D2BB36C51E7   ← candidate: Fluidra GATT Service
0b8d3f3e-d479-4d54-9973-1aa2757d9013
0FB6258A-9206-4923-9A2D-1D2AD6EE7ADB
2970dc32-feda-480d-98ae-63fee84da7c6
565acab9-c34d-495d-bb01-4ceacaceca11
574b3234-dafc-4d33-9900-c318b63bd81b
61DA462F-F17B-40C8-A705-ED12C67F741A
6412403b-b331-4a25-a579-276d88ea1df6
6eb8c84d-5942-4a20-8db2-51a7352c6305
8487A256-78C7-4C75-96E1-70ACF6A6E925
902D8EC9-05AC-4C6C-BB66-25DCAA14E072
9338d072-e28b-2e34-7497-6dc5bb2c411c
9669ee38-91d3-45ab-e560-c8944f0340b5
99b848f0-fa17-4586-8026-73b30577a35f
b01348e9-5fc5-7e75-65ba-88dd66bb42c0
b30497c5-6714-4c44-ae29-ad38d6d1f4dc
c23621da-5e85-40ef-bc25-585a6606d737
ca7b1d0d-0964-416b-b45c-1ec986cbfefe
d3d5a711-5d87-4b60-917b-01ccfdebb5ff
da2e7828-fbce-4e01-ae9e-261174997c48
F1B22A16-456E-4825-8089-E02F74FC9AC1
f7bf3564-fb6d-4e53-88a4-5e37e0326063
fa3bc7ae-03a1-4b05-8b47-78725ddaa4f8
```

**Key implication:** Silicon Labs OTA DFU Service UUID (`1d14d6ee...`) is confirmed present.
This is the standard Silicon Labs Bluetooth DFU service used with `mcumgr` / OTA Update CLI.
Custom firmware can be flashed if signature verification is disabled.

---

## Additional Symbols (iteration 3)

### API Environments (all URLs confirmed from binary)
| Environment | REST Base | WebSocket |
|-------------|-----------|-----------|
| Production | `https://api.fluidra-emea.com/generic` | `wss://ws.fluidra-emea.com` |
| Staging | `https://stage.api.fluidra-emea.com/generic` | `wss://stage.ws.fluidra-emea.com` |
| Dev | `https://dev.api.emea-iot.aws.fluidra.com/generic` | `wss://dev.ws.fluidra-emea.com` |
| Test | `https://test.api.emea-iot.aws.fluidra.com/generic` | `wss://test.ws.fluidra-emea.com` |

### IoT Configuration Keys
```
fluidra-emea-fluidra-pool-prod      ← AWS IoT Thing Group / Cognito pool
fluidra-emea-fluidra-pool-staging
fluidra-emea-fluidra-pool-dev
fluidra-emea-fluidra-pool-test
fluidra-emea-fluidra-pro-auth0-prod ← "Pro" variant uses Auth0 (different auth!)
fluidra-emea-fluidra-pro-auth0-dev
```

### Transport Classes
```
FluidraAuthTransport       → dedicated auth transport (token management)
FluidraSppTransport        → Bluetooth SPP (Serial Port Profile) transport
LumiplusUdpService         → Lumiplus lights have their OWN UDP service
LumiplusWifiClient         → Lumiplus also has WiFi direct client
LumiplusAccessCodeTransport → Lumiplus BLE access code transport
NodonTransport             → Nodon relay transport (Zigbee)
FlutterReactiveBleOtaTransport → BLE OTA (open source flutter_reactive_ble)
FlutterReactiveBleConnector
FlutterReactiveBlePlugTransport → Nodon plug transport over BLE
```

**Key implication:** `LumiplusUdpService` + `LumiplusWifiClient` confirms there are at least
**two** UDP implementations in the app (iQBridge RS local UDP + Lumiplus direct UDP).
The Lumiplus UDP code can be compared against iQBridge UDP to understand the protocol family.

### Hardware QR Pairing
```
FluidraHpcQrCode           → HPC = Hardware Pairing Code (QR-based device pairing)
FluidraHpcQrCode.fromSplits
FluidraQrCode
FluidraQrCode.fromSdkQr
NodonCode
NodonCode.fromQr           → Nodon also uses QR pairing
```

---

## Full Ghidra Analysis

> Full analysis output at `docs/RE-libapp-functions.txt` (generated by Ghidra headless).
> Script: `scripts/ghidra_strings.py`
> Run: `$GHIDRA/support/analyzeHeadless /tmp/ghidra_fluidra FluidraProject -process libapp.so -postScript scripts/ghidra_strings.py`
