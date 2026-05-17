# Subagent findings: Fluidra local UDP / message protocol

Date: 2026-05-15
Scope: static review of `/home/roagert/projects/fluidra-re` and `/home/roagert/projects/ha-fluidra-pool` for possible direct local heat-pump commands. No secrets included. No live writes performed.

## Bottom line

- Local UDP support is real in the Fluidra Android app, but the evidence points to it being a transport option inside the app's `MobileCommandAndControl` abstraction, most likely for iQBridge/Lumiplus-style devices.
- The known user device type is `amt` (Amitime heat pump with integrated Wi-Fi). Existing live/API notes say `commandAndControl.localUdp` was not present for that device. For `amt`, cloud REST + WebSocket is confirmed; direct UDP is unconfirmed and should not be assumed.
- The current `local_client.py` is explicitly a speculative stub. Treat it as unsafe for actual commands until traffic capture or function-level AOT decompilation confirms framing, ports, key source, payload encoding, and ACK semantics.

## Static evidence mined

### Classes / objects

High-signal strings in `libapp.so` / docs:

- `MobileCommandAndControl`
- `MobileCommandAndControlCloud`
- `MobileCommandAndControlLocalUdp`
- `MobileCommandAndControlBle`
- `LocalUdp`
- `LocalUdp.fromJson`
- `UiConfig(commandAndControl:`
- `commandAndControl`

Interpretation:

- The app parses a `commandAndControl` config object from API/uiconfig/device data.
- `localUdp` is not simply a globally hardcoded mode; it appears to be a per-device capability/config returned by API.
- For `amt`, prior live findings state this object/field was not found, so local UDP should be feature-gated on observed API data only.

### UDP and protocol functions

High-signal strings:

- `initUdpDeviceListener`
- `sendUDPCommand`
- `udpService`
- `udpDevbar`
- `localUdpB`
- `FluidraMessageProtocol`
- `MagicNumber`
- `payloadIntBE`
- `payloadIntLE`
- `payloadString`
- `payload_type`
- `buildWritePayload`
- `requestPayload`
- `createDynamicValuePayload`
- `protocolReadComponentId`
- `reportChannelReadComponentId`
- `keyComponentId`
- `desiredOrReported`
- `encodeComponent`
- `decodeComponent`

Interpretation:

- There is a custom binary message layer with a magic constant and protocol enum.
- Payload building appears typed: integer big-endian, integer little-endian, string, and a payload type discriminator all exist.
- Read and write payloads are separate concepts (`requestPayload` vs `buildWritePayload`), and component encoding/decoding is centralized.
- The packet almost certainly is not just `component_id + value`; it likely carries message protocol, component key, desired/reported selector, payload type, and possibly packet sequencing.

### Integrity / auth / key hints

High-signal strings:

- `udpKey`
- `updateUPDkey`
- `generateWorkingKey`
- `keyCipherAlgorithm`
- `hmac`, `hmac256`, `hmac512`
- `getCrc32Byte`, `updateCrc`, `sv4crc`
- `totalPackets`, `packetIndex`, `addPacket`, `addFrame`

Interpretation:

- UDP auth is likely HMAC-SHA256, but the exact covered bytes, key material, and truncation/placement are not proven.
- `udpKey` appears to be an API/config field or derived runtime field. `updateUPDkey` suggests it may rotate or be refreshed rather than derived statically from serial number alone.
- CRC32 is likely present, but endian, initial value, final xor, and covered region are unconfirmed.
- Multi-packet framing is possible.

### Ports

Docs list numeric string candidates:

- `9003`, `8902`, `9090`, `9298`, `5781`, `5750`, `1850`, `1801`, `1800`, `3844`, `3317`

Interpretation:

- These are only string candidates, not confirmed port assignments.
- Existing docs explicitly say port should come from `localUdp` API data when present, not a hardcoded constant.
- For the `amt` heat pump, component ID 2 exposes LAN IP in cloud components, but no local UDP port/token was confirmed.

### Device support: `amt`

Prior project findings say:

- Device type: `amt` (Amitime heat pump)
- Cloud REST read/write confirmed.
- WebSocket subscription confirmed.
- `commandAndControl.localUdp` not present for the device during live API debug.
- `amt` may have BLE SPP provisioning; BLE control remains a separate investigation.

Assessment:

- Confidence high that the app contains UDP support.
- Confidence medium-high that `amt` does not expose the same `commandAndControl.localUdp` path as iQBridge RS.
- Confidence low that any direct UDP command path exists for the current `amt` device without additional LAN capture/scan evidence.

## Current `local_client.py` comparison

### Plausible pieces

- Uses UDP datagrams via asyncio: plausible transport.
- Includes CRC32 and HMAC-SHA256: both are supported by strings.
- Treats local mode as optional/fallback: correct architectural direction.
- Has a timeout/no-response failure path: useful for probing.

### Likely wrong or unsupported by evidence

- Hardcoded `UDP_MAGIC = 0x12 0x34`: unsupported. Static strings only show `MagicNumber`, not the bytes.
- Hardcoded protocol IDs (`0x03`, `0x02`) and command IDs (`0x01`, `0x02`): unsupported.
- Header layout `[magic][protocol:1][cmdId:2 BE][payloadLen:4 BE]`: unsupported.
- CRC32 little-endian placement/coverage: unconfirmed.
- HMAC placement and coverage (`body + checksum`) with UTF-8 token key: unconfirmed.
- Token derivation candidates from serial/`fluidra`: speculative and likely wrong if `udpKey` is returned/refreshed by API.
- Payload encoding as `>HI` (`component_id:uint16`, `value:uint32`): probably too simple. Strings indicate typed payloads, `keyComponentId`, `desiredOrReported`, `payload_type`, and component encode/decode helpers.
- `device_id` argument is unused; likely not correct for a real per-device command protocol unless omitted by design.
- Marking `connect()` as available without sending any probe can produce false positives for UDP because UDP connect does not prove remote support.
- Logging raw packet hex can leak message authentication material and should be gated/redacted in normal HA logs.

## Safe read-only probe design

Do not send write commands or guessed authenticated packets. Prefer passive/observational probes first.

### Phase 0: collect capability shape via cloud API

- Add a diagnostic path that fetches device detail and uiconfig endpoints already used by the app/integration.
- Redact tokens/keys, but preserve object shape:
  - whether `commandAndControl` exists
  - which transports exist: `cloud`, `localUdp`, `ble`, `bleDirect`, `bleBroadcaster`, `bleCommandAndControl`
  - for `localUdp`, preserve only field names/types, not token/key values
- Gate all UDP implementation behind presence of `commandAndControl.localUdp`.

### Phase 1: LAN service discovery, no writes

From the same LAN as the device:

- ARP/ping to verify the device IP from component 2 is still current.
- TCP connect scan for common HTTP/API ports and documented candidates.
- UDP discovery should be passive first; if active, only send zero-length datagrams or app-confirmed read/request frames later.
- Suggested ports to observe/scan: `9003,8902,9090,9298,5781,5750,1850,1801,1800,3844,3317` plus HTTP ports.

### Phase 2: passive capture while official app is used

Best evidence path:

- Put phone and heat pump/device on same Wi-Fi/VLAN.
- Capture at router/AP, mirrored switch port, or host running a monitor bridge.
- Use filters limited to phone IP and device IP; capture UDP plus DNS/ARP/mDNS/SSDP if discovery matters.
- In the official app, perform read-only actions first:
  - open device screen
  - refresh/status view
  - view component/status pages
  - avoid toggles and setpoint changes unless explicitly permitted later
- Record timestamps and app UI action labels, not secrets.
- Check whether any UDP datagrams occur between phone and device. If none, `amt` likely uses cloud-only local UI.

### Phase 3: app-induced but low-risk writes only if explicitly allowed later

Not part of this static task, but if the owner authorizes live testing:

- Use harmless reversible commands, e.g. set setpoint to its current value, not power/mode changes.
- Capture official app packets for that action.
- Compare packet deltas against known component ID/value from cloud state.

### Phase 4: derive read-only frame builder

Only after a captured official UDP read/request frame exists:

- Identify magic bytes, length fields, protocol enum value, CRC coverage, HMAC coverage, and nonce/timestamp/sequence fields.
- Implement decoder first.
- Implement read-only request replay only if it is demonstrably a status request and safe.
- Do not implement writes until confirmed by official-app captures and guardrails.

## CLI implementation recommendations

### Near term: do not ship direct UDP writes

- Keep cloud REST/WS as the supported path for `amt`.
- Disable or remove automatic use of `local_client.py` until confirmed.
- If retained, rename it to make status clear, e.g. `local_udp_experimental.py`, and ensure no code path calls `set_component` automatically.

### Add a safe `discover-local` CLI/subcommand

Recommended outputs:

- device ID/type/model/SKU/firmware (redacted as needed)
- cloud component with LAN IP (if present)
- `commandAndControl` transport names and field types only
- TCP open ports
- UDP passive-observation instructions or capture summary
- no tokens, no `udpKey`, no raw HMAC packets by default

Modes:

- `--cloud-capabilities`: only cloud GETs, no LAN packets.
- `--lan-scan`: TCP scans and optional UDP empty-probe only.
- `--pcap FILE`: offline analyze official-app capture.
- `--decode-only`: decode candidate packets; never send.
- `--allow-write`: absent by default and still should refuse guessed/unknown protocols.

### Protocol implementation shape once confirmed

- Model packets as parsed frames, not ad hoc byte concatenation:
  - magic/version/protocol
  - packet index/total if present
  - payload type
  - component key/id
  - desired/reported selector
  - typed value bytes
  - CRC field
  - HMAC field
- Read key/host/port from API `localUdp` only. Do not derive keys from serial unless capture/API proves it.
- Separate `decode_frame()`, `verify_crc()`, `verify_hmac()`, and `build_request_payload()` from `send_*()` functions.
- Unit-test with captured, redacted hex fixtures where HMAC/key bytes are removed or synthetic.

## Confidence levels

- App contains a local UDP command path: high.
- UDP path uses magic + CRC + HMAC-SHA256: medium-high.
- Port is 9003: low-medium; candidate only unless returned by `localUdp`.
- `udpKey` is API-provided/refreshed rather than serial-derived: medium.
- Current `amt` device supports `commandAndControl.localUdp`: low based on existing live/API notes.
- Current `local_client.py` packet format is correct: low.
- Safe next step is passive capture + capability-shape extraction: high.
