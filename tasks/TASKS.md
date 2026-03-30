# Task Index — ha-fluidra-pool

> Auto-managed by autonomous engineer pipeline.
> Last updated: 2026-03-30

---

## P0 — Blocking

*None currently.*

---

## P1 — Core

- [x] [TASK-001](TASK-001.md) — WebSocket real-time updates *(done 2026-03-29)*
- [ ] [TASK-002](TASK-002.md) — Local UDP client (iQBridge RS) ⚠️ BLOCKED: auth token expired, needs new `fluidra_debug.py` run
- [ ] [TASK-003](TASK-003.md) — Dual-mode coordinator (local → WS → REST) *(depends TASK-002)*
- [x] [TASK-004](TASK-004.md) — Ghidra + strings analysis of libapp.so *(done 2026-03-30)*

---

## P2 — Enhancement

- [x] [TASK-005](TASK-005.md) — BUG-001: Smart Auto mode display fix *(done 2026-03-29)*
- [x] [TASK-006](TASK-006.md) — BUG-002: Remove deprecated consumer sensor *(done 2026-03-29)*
- [ ] [TASK-007](TASK-007.md) — BUG-003: Fix diagnostic error sensor attributes
- [x] [TASK-008](TASK-008.md) — FEAT-001: Chlorinator sensors (pH/ORP/salinity/chlorine) *(done 2026-03-29)*
- [x] [TASK-009](TASK-009.md) — FEAT-002: Water temperature standalone sensor *(done 2026-03-29)*
- [ ] [TASK-010](TASK-010.md) — Config flow: connection_mode selector

---

## P3 — Nice-to-Have

- [ ] [TASK-011](TASK-011.md) — FEAT-003: MQTT bridge
- [x] [TASK-012](TASK-012.md) — FW-001: Nodon firmware bundled in APK (no separate URL) *(done 2026-03-30)*
- [x] [TASK-013](TASK-013.md) — FW-002: Firmware binary analysis → see docs/FIRMWARE.md *(done 2026-03-30)*
- [ ] [TASK-014](TASK-014.md) — FW-003: Custom firmware design (EFR32 Gecko SDK)

---

## Dynamically Generated

- [ ] [TASK-DYN-001](TASK-DYN-001.md) — Recover Fluidra credentials + re-run fluidra_debug.py *(TASK-002 blocker)*
- [ ] [TASK-DYN-002](TASK-DYN-002.md) — STM32 serial protocol RE (needed for custom EFR32 firmware)
