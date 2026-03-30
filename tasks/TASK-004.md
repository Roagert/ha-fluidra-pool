---
id: TASK-004
title: Ghidra headless analysis of libapp.so
priority: P1
status: in-progress
depends_on: []
branch: task/TASK-004-ghidra-analysis
iteration: 1
max_iterations: 3
created: 2026-03-30
---

## Description
Run Ghidra 12.0.4 headless analysis on `libapp.so` (ARM64 Dart AOT snapshot, 32 MB) to extract
function names and any decompilable logic related to local UDP protocol, FluidraMessageProtocol enum values,
BLE GATT UUIDs, and OTA firmware update flow.

## Acceptance Criteria
- [ ] Ghidra headless completes without crash
- [ ] Function name list extracted to `docs/RE-libapp-functions.txt`
- [ ] RE report `docs/RE-libapp.md` written with strings of interest
- [ ] FluidraMessageProtocol enum values identified (if decompilable)
- [ ] BLE base UUID extracted from binary data

## Implementation Notes
- Binary: `~/projects/fluidra-re/native/lib/arm64-v8a/libapp.so`
- Ghidra: `/opt/ghidra/ghidra_12.0.4_PUBLIC/`
- ARM64 ELF — select ARM Cortex language in Ghidra
- Dart AOT: functions are dart stubs, not C symbols — focus on strings + data sections
- Key targets: `FluidraMessageProtocol`, `MagicNumber`, `udpKey`, `sendUDPCommand`

## Execution Log
| Iteration | Outcome | New Tasks Generated | Notes |
|-----------|---------|---------------------|-------|
| 1 | running | — | headless analysis started |

## Output Artifacts
- `docs/RE-libapp-functions.txt`
- `docs/RE-libapp.md`
