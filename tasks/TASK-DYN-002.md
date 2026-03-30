---
id: TASK-DYN-002
title: Reverse engineer STM32 serial protocol (EFR32 ↔ STM32)
priority: P3
status: todo
depends_on: [TASK-014]
branch: task/TASK-DYN-002-stm32-serial-re
iteration: 0
max_iterations: 10
created: 2026-03-30
spawned_from: TASK-013 (FW-002 firmware analysis)
signal: "STM32 Version %d.%d.%d — second MCU communicates with EFR32 over UART serial"
---

## Description

The Nodon SIN-2-in-1 has two MCUs:
- **EFR32** (radio: Zigbee + BLE) — this is the GBL firmware we analyzed
- **STM32** (host: relay control, scheduler, buttons, LED)

The EFR32 receives BLE commands then relays them to STM32 via UART serial using an
internal `[SERIAL]` framed protocol. To build custom firmware that controls the physical
relays, we must understand this serial protocol.

## Acceptance Criteria
- [ ] UART frame structure documented (header, length, CRC, payload format)
- [ ] At least 5 command types decoded (relay on/off, get status, etc.)
- [ ] `SERIAL_PROTOCOL.md` written with packet format + command table

## Implementation Notes

### Method 1: Ghidra analysis of EFR32 firmware
Load `v4_7_0.gbl` into Ghidra with EFR32 processor spec.
Find USART TX/RX functions — decompile the serial frame builder.

```bash
GHIDRA=/opt/ghidra/ghidra_12.0.4_PUBLIC
$GHIDRA/support/analyzeHeadless /tmp/ghidra_nodon NodonProject \
  -import /path/to/v4_7_0_extracted_app.bin \
  -processor "ARM:LE:32:Cortex" \
  -postScript scripts/ghidra_strings.py
```

### Method 2: Physical UART tap
If hardware is available: tap UART TX/RX pins between EFR32 and STM32 with logic analyzer.
Trigger known BLE commands and capture the resulting serial frames.

### Method 3: Debug log parsing
The firmware logs serial activity:
```
[SERIAL] Bad frame crc %d %d
[serial] retry %dms for %d
debug protocol : id %x, type %x, frame %x
```
The `debug protocol: id %x, type %x, frame %x` string confirms the frame has at least
`id`, `type`, and `frame` fields.

## Known Frame Properties (from strings)
```
[SERIAL] Payload parameter is too long  → max payload length exists
[SERIAL] Error allocation payload       → dynamic allocation
[SERIAL] Error frame size               → frame size validation
[SERIAL] No valid data                  → data validation
[SERIAL] Bad ack crc                    → ACK frames have CRC
[SERIAL] Ack without command            → ACK/CMD pair protocol
[SERIAL] Bad frame crc %d %d           → data frame CRC (expected vs got)
[SERIAL] Duplicate %d                   → sequence number dedup
debug protocol : id %x, type %x, frame %x  → frame has id + type + frame fields
```

Frame appears to be: `[id][type][frame][payload][crc]`
