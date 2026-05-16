# Fluidra Local Solution — Next Build Plan

Goal: move from the confirmed cloud solution to a verified local/non-cloud path for `LG24440781` without guessing control packets or risking unintended heat-pump changes.

## Current confirmed state

- Cloud control is solved through Fluidra EMEA REST:
  - `GET /generic/devices/LG24440781/components?deviceType=connected`
  - `PUT /generic/devices/LG24440781/components/{13,14,15}?deviceType=connected`
- Device LAN identity from cloud/components:
  - IP: `192.168.1.29`
  - Serial: `LG24440781`
  - Type: `amt`
  - Firmware: `2.5.0`
  - Signature: `BXWAB0603494724050`
- Previous MQTT trail was false: `192.168.1.11:1883` was Home Assistant/Mosquitto, not the heat pump.
- Read-only LAN probing found the heat pump reachable by ping; common TCP ports were closed.

## Local solution hypotheses

### 1. Passive LAN/UDP capture — primary next step

The official iAquaLink+ app binary contains generic local UDP control strings (`MobileCommandAndControlLocalUdp`, `sendUDPCommand`, `udpKey`, HMAC/CRC helpers), but the `amt` snapshot does not expose `commandAndControl.localUdp` for this device.

Evidence needed:

- Does the phone app send any LAN UDP packet to/from `192.168.1.29` while performing a cloud-visible command?
- Does the heat pump emit broadcast/multicast discovery traffic?
- Is any local packet correlated with writes to components `13`, `14`, or `15`?

Safe capture command on a router/AP/Linux bridge:

```bash
sudo tcpdump -i any -nn -s0 -w fluidra-local.pcap \
  'host 192.168.1.29 and (udp or arp or icmp)'
```

Suggested harmless capture sequence:

1. Start capture.
2. Open iAquaLink+ on the same LAN as the heat pump.
3. Refresh the heat-pump screen.
4. Change setpoint by +1 °C in the official app.
5. Restore setpoint.
6. Stop capture.
7. Compare packet timestamps with cloud component `15` timestamps.

Do not send crafted UDP until a packet layout/key is recovered from real traffic or code.

### 2. BLE SPP investigation — secondary

Device API confirms provisioning BLE SPP:

- Service UUID: `4e7763c4-211b-47b8-88df-cd869df32c48`
- RX UUID: `54c4dfef-4e04-4c42-9c33-06a6af86280c`
- TX UUID: `760f6551-4156-4829-8bcc-62591b1eb948`
- Protocol: `SPP`
- Pairing mode: `auto`

Safe BLE steps:

1. Passive scan for advertisements.
2. Optional read-only GATT service discovery.
3. Do not write RX characteristic until runtime control is proven.

Useful tooling later:

```bash
bluetoothctl scan on
bluetoothctl info <MAC>
# or bleak-based service discovery from Python, read-only only
```

### 3. Static APK/Dart AOT recovery — supporting path

Next code-recovery targets:

- `udpKey`
- `generateWorkingKey`
- `updateUPDkey` / typo-preserved app string
- `sendUDPCommand`
- `FluidraMessageProtocol`
- `MagicNumber`
- CRC32 and HMAC-SHA256 helpers
- SPP framing variants `SPP8`, `SPP32`, `SPP8X`

Expected output:

- packet framing
- key derivation
- whether `amt`/`BXWAB` enables local runtime control
- command IDs corresponding to components `13`, `14`, `15`

## CLI work now available

- `scripts/fluidra_cloud.py`: cloud status and guarded writes.
- `scripts/fluidra_local.py`: read-only LAN discovery, MQTT negative validation, component decoder, firewall-plan generator.

Useful local commands:

```bash
python3 scripts/fluidra_local.py --host 192.168.1.29 discover
python3 scripts/fluidra_local.py status tests/fixtures/lg24440781_components.json
python3 scripts/fluidra_local.py --host 192.168.1.29 firewall-plan --router openwrt --lan-cidr 192.168.1.0/24
```

Do not apply firewall isolation until a local path is proven, otherwise app/cloud control may be lost.

## Success criteria for local solution

A local solution is not considered confirmed until at least one of these is true:

1. Captured local packet(s) can be replayed/decoded and correlated with a harmless setpoint change.
2. APK/AOT recovery proves the exact packet format and key derivation for this `amt` device, then a read/status command works locally.
3. BLE read/control protocol is recovered and a read-only status command works without cloud.

Only after read-only local status works should local writes be attempted, and the first write should be a reversible setpoint +1 °C / restore test.
