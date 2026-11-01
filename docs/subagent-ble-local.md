# Subagent BLE Local Investigation — Fluidra/Amitime `amt`

Date: 2026-05-15
Device context: Fluidra/Amitime `amt`, SN `LG24440781`, firmware `2.5.0`.
Safety boundary used: read-only host/tool inspection and BLE advertisement scanning only. No BLE connection, pairing, GATT read/write, or heat-pump control writes were attempted.

## 1. Local Bluetooth tooling

Host has a working Bluetooth adapter and BlueZ CLI tools:

- `bluetoothctl`: `/usr/bin/bluetoothctl`, version `5.72`
- `btmgmt`: `/usr/bin/btmgmt`
- Adapter: `hci0`, USB MediaTek, address `4C:82:A9:F0:83:8E`, state `UP RUNNING PSCAN`, HCI/LMP `5.4`
- Python `bleak`: **not installed** (`ModuleNotFoundError: No module named 'bleak'`)

Implication: passive CLI scanning is possible now. Python experiments using Bleak require installing `bleak` first.

## 2. Passive BLE advertisement scan

Command used:

```bash
timeout 25s bluetoothctl --timeout 20 scan le
```

Observed devices included many generic/random-address BLE advertisements, plus named devices:

- `F3:33:8D:C0:EA:4D` — `S18 C706 LE`, RSSI approx `-86` to `-79`, manufacturer `0x05a7`
- `E1:A1:68:08:F5:60` — `S19 705F LE`, RSSI approx `-79/-78`, manufacturer `0x05a7`
- several more `S18 .... LE` devices with manufacturer `0x05a7`
- `F3:C6:5D:17:49:AB` — `TT214H BlueFrog`, RSSI approx `-76`
- `4C:EB:D6:5A:9C:B6` — `EHWRVR42`
- nearby TV/phone/random-address devices

No advertisement name explicitly matched `Fluidra`, `Amitime`, `amt`, `LG24440781`, or the configured provisioning service UUID. `bluetoothctl scan le` output did not expose service UUIDs for matching against `4e7763c4-211b-47b8-88df-cd869df32c48`.

Caveats:

- The heat pump may not advertise except during provisioning/pairing/setup mode.
- It may advertise under a cloud-id/type-derived name rather than `Fluidra`/serial.
- A better passive scan with Bleak or `btmon` is needed to decode service UUIDs/service-data/manufacturer-data cleanly.

## 3. Artifact mining — BLE SPP/provisioning protocol evidence

### Device/API evidence already documented

`PROTOCOL_FINDINGS.md` confirms for this `amt` device:

- It is an Amitime heat pump with integrated Wi-Fi, not iQBridge RS.
- `commandAndControl.localUdp` is not present for this device.
- BLE is present under `info.configuration.capabilities.provisioning.ble`:
  - Service UUID: `4e7763c4-211b-47b8-88df-cd869df32c48`
  - RX UUID: `54c4dfef-4e04-4c42-9c33-06a6af86280c`
  - TX UUID: `760f6551-4156-4829-8bcc-62591b1eb948`
  - Protocol: `SPP`
- Binary/app strings mention SPP framing variants: `SPP8`, `SPP32`, `SPP8X`.

### App string-table evidence

`docs/RE-libapp.md` and `docs/RE-libapp-ghidra-strings.txt` contain these relevant strings/classes:

- Command/control model:
  - `MobileCommandAndControlBle`
  - `getCommandAndControl`
  - `sendCommand`
  - `sendBleCommands`
  - `initComponentsSubscription`
  - `openComponentsListener`
  - `encodeComponent` / `decodeComponent`
  - `writeComponent` / `writeComponents`
- BLE protocol families:
  - `FluidraBleMessageProtocol`
  - `BleCommandAndControlMessageProtocol`
  - `BleCommandAndControlProtocol`
  - `BleConnectMessageProtocol`
  - `BleConnectProtocol`
  - `BlePairingMessageProtocol`
  - `BlePairingProtocol`
- BLE provisioning/scanning:
  - `BleProvisioningInfo(serviceUuid:`
  - `BleProvisioningService`
  - `BluetoothProvisioningService|_getDeviceInformationV1/V2`
  - `BluetoothProvisioningService|_scanWifiNetworksV1/V2`
  - `BluetoothProvisioningService|_connectToWifiNetworkV1/V2`
  - `BluetoothProvisioningService|_setCloudRegionV2`
  - `BluetoothProvisioningService|_setTimestampV1/V2`
  - `BluetoothProvisioningService|_setTimezoneV1/V2`
  - `BluetoothScannerFluidraDeviceExtension|_matchesCloudId`
  - `Cannot parse cloudId from device name:`
  - `Cannot parse deviceType or cloudId from device name:`
- Access-code path:
  - `Access Code (min 4 chars)`
  - `Access code service`
  - `Access code characteristic`
  - `Access code RX characteristic`
  - `Access code sent for ...`
  - `Access code acknowledgement received for ...`
  - `Access code result`
  - `Access code is incorrect`
  - `BLE access code info required but not provided`
  - `BleAccessCodeConfiguration`
  - `BlePairingAccessCode`
  - `FlutterReactiveBleAccessCodeTransport`
- SPP/framing:
  - `FluidraSppTransport`
  - `StreamedSppTransport`
  - `SppCharacteristics`
  - `SppResponse`
  - `SppVersion`
  - `SPP send`
  - `SPP notification in MAIN subscription`
  - `SPP32`
  - `SPP8 packet index must be between 1 and 255.`
  - `SPP8 payload too large (`
  - `SPP8 supports between 1 and 255 packets.`
  - `SPP8X`
  - `_Spp32@...`, `_SppV1@...`, `_buildSppFrames@...`
- Generic GATT component paths:
  - `DeviceComponentInfoBleAdvertisingRead*`
  - `DeviceComponentInfoBleLegacyGatt*`
  - `LegacyGattReadInformation`, `LegacyGattWriteInformation`
  - `rxCharacteristicUuid`, `txCharacteristicUuid`, `rxServiceUuid`, `txServiceUuid`, `rxUuid`, `txUuid`, `rxProtocol`, `txProtocol`, `serviceUuid`

### Access-code / pairing requirement

There is strong evidence that BLE operations are access-code gated:

- Strings explicitly require BLE access-code info.
- Pairing protocol objects include `BlePairingAccessCode`.
- Access-code transport listens for acknowledgements and reports incorrect code.
- Related firmware notes for a different Fluidra/Nodon BLE command interface state all commands require `CMD_SET_ACCESS_CODE` and frame validation has CRC/seed/replay protections. That firmware evidence may not be the `amt` heat-pump firmware, but it is consistent with app-level access-code gating.

## 4. Assessment: local CLI datapoints/control via BLE?

Current confidence:

- **BLE provisioning is confirmed** for this `amt` device by API capabilities and app strings.
- **BLE command-and-control support exists in the app architecture** (`MobileCommandAndControlBle`, `sendBleCommands`, component encode/decode, component subscription strings).
- **For this specific `amt` instance, the API evidence seen so far only exposes BLE under provisioning capabilities**, not under `commandAndControl`. This means the app may only use BLE for onboarding/Wi-Fi provisioning for this model/firmware.
- **No passive scan match was found** in this run, so the local adapter did not identify the target heat pump advertising in normal operation.

Recommendation: treat BLE local datapoints/control as **promising but unproven**. It is not ready for a local CLI yet. The near-term path is to prove whether the heat pump exposes the SPP service in normal mode and whether the cloud API returns a `MobileCommandAndControlBle` object for this device.

## 5. Exact next experiments

All experiments below should remain read-only until explicit approval is given for connecting/pairing/writing.

### A. Install/read-only scan with Bleak

Install `bleak` in a venv or user environment, then perform a passive scan printing names, addresses, RSSI, service UUIDs, service data, and manufacturer data. Target matches:

- advertised service UUID `4e7763c4-211b-47b8-88df-cd869df32c48`
- name containing `Fluidra`, `Amitime`, `amt`, `LG24440781`, a cloud-id, or parseable device type/cloud id
- manufacturer/service data that changes when heat pump is put into provisioning mode

Suggested safe scan script:

```python
import asyncio
from bleak import BleakScanner

TARGET_UUID = '4e7763c4-211b-47b8-88df-cd869df32c48'

async def main():
    def cb(device, adv):
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        name = adv.local_name or device.name or ''
        hit = TARGET_UUID in uuids or any(s.lower() in name.lower() for s in ['fluidra', 'amitime', 'amt', 'lg24440781'])
        if hit:
            print('MATCH', device.address, name, adv.rssi, uuids, adv.manufacturer_data, adv.service_data)
        else:
            print('ADV', device.address, name, adv.rssi, uuids, adv.manufacturer_data, adv.service_data)
    scanner = BleakScanner(cb)
    await scanner.start()
    await asyncio.sleep(60)
    await scanner.stop()

asyncio.run(main())
```

### B. Repeat scan with heat pump in provisioning/add-device mode

If the normal-mode scan does not show the service UUID, put the device into the vendor-documented add/provisioning mode and repeat passive scan. Do not connect yet. Compare:

- advertisement name
- service UUID list
- manufacturer/service data
- whether the target SPP UUID appears only in provisioning mode

### C. Cloud/API shape check

Capture the full device object for SN `LG24440781` and inspect:

- `info.configuration.capabilities.provisioning.ble`
- any `commandAndControl.ble` or `MobileCommandAndControlBle`-equivalent object
- any `accessCode`, `mobileInfo`, `cloudId`, or BLE access-code configuration fields
- component `ble` metadata (`DeviceComponentInfoBleAdvertisingRead`, `DeviceComponentInfoBleLegacyGattRead/Write`)

If there is no BLE command-and-control object, CLI control over BLE is likely not supported for `amt` outside provisioning.

### D. After explicit approval only: connect and enumerate GATT

A GATT service/characteristic enumeration normally requires a BLE connection but no writes. It should still wait for explicit approval because it may affect device/app pairing state. If approved, enumerate services and verify the SPP UUID and RX/TX properties.

### E. After explicit approval only: SPP read-only handshake

Only if GATT enumeration confirms the SPP service and an access code is available/authorized:

1. Subscribe/notify on TX UUID.
2. Do not write access code or provisioning data until approved.
3. If approved, send the minimum documented access-code/hello request captured from app logs or RE, then attempt read-only commands only (`get device information`, `read component`, not `writeComponent`).

## Conclusion

BLE is confirmed as the `amt` provisioning channel and the app contains a BLE command-and-control stack with SPP framing. However, for this specific heat pump the known API evidence places BLE under provisioning, and a passive scan did not identify the device/service in normal mode. The best next step is a richer passive Bleak scan, ideally both normal and provisioning mode, then a cloud API shape check for `commandAndControl.ble`. Until those two checks are positive, BLE should be considered provisioning-first rather than a proven local datapoints/control CLI path.
