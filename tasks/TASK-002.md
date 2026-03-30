---
id: TASK-002
title: Local UDP client for iQBridge RS
priority: P1
status: todo
depends_on: [TASK-004]
branch: task/TASK-002-local-udp
iteration: 0
max_iterations: 10
created: 2026-03-30
---

## Description
Implement `local_client.py` — an asyncio UDP client that sends commands directly to iQBridge RS
on the LAN, bypassing the cloud entirely. The `commandAndControl.localUdp` field from the cloud API
provides host, port, and auth token.

## Acceptance Criteria
- [ ] `LocalUDPClient` class with `async connect()`, `async send_command(component_id, value)`, `async disconnect()`
- [ ] Packet format matches Cipher hypothesis (or corrected from live tcpdump capture)
- [ ] Auth token verification against serial-derived HMAC
- [ ] Round-trip command latency < 500 ms on LAN
- [ ] Graceful fallback if UDP socket fails

## Implementation Notes
- Packet hypothesis: `[0x12 0x34][protocol:1][cmdId:2 BE][len:4 BE][payload][CRC32:4][HMAC-SHA256:32]`
- Port hypothesis: 9003 (verify with nmap scan first)
- Auth: HMAC-SHA256(serial, "fluidra") — test against live token from debug script
- Use `asyncio.DatagramProtocol` for non-blocking UDP
- File: `custom_components/fluidra_pool/local_client.py` (new)

## Blocker
Requires `fluidra_debug.py` output showing actual `commandAndControl.localUdp` JSON.
Without live token + host, packet format remains hypothesis.

## Execution Log
| Iteration | Outcome | New Tasks Generated | Notes |
|-----------|---------|---------------------|-------|
| — | todo | — | blocked on live capture |

## Output Artifacts
- `custom_components/fluidra_pool/local_client.py`
