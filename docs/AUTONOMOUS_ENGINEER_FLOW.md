# Autonomous Engineer Flow — ha-fluidra-pool

> Documents how the autonomous engineering pipeline was applied to this project.
> Date: 2026-03-30

---

## Overview

The autonomous engineer pipeline executes in 7 phases:

```
GOAL (local-first HA integration + RE)
       │
       ▼
 Phase 1: REASON + PRD ──────────────► docs/PRD.md
       │
       ▼
 Phase 2: TASK TREE ─────────────────► tasks/TASKS.md + tasks/TASK-*.md
       │
       ▼
 Phase 3: GHIDRA RE ─────────────────► docs/RE-libapp.md
       │
       ▼
 Phase 4: RALPH LOOP (per task) ─────► commits per iteration
       │
       ▼
 Phase 5: DYNAMIC TASKS ─────────────► tasks/TASK-DYN-*.md (from loop output)
       │
       ▼
 Phase 6: SUMMARY ───────────────────► docs/SUMMARY.md
       │
       ▼
 Phase 7: CI/CD ─────────────────────► .github/workflows/improvement.yml
```

---

## Phase 1: Reasoning Protocol

### Goal Clarification
Build a local-first Home Assistant integration for Fluidra Pool heat pump controllers.
Replace cloud polling (15 min) with local LAN UDP (<100 ms) + cloud WebSocket (<2 s).

### Constraint Mapping
| Type | Constraint |
|------|-----------|
| Hard | Python 3.11+, HA 2024.1+, asyncio event loop |
| Hard | No cloud calls for device control in local mode |
| Hard | Must not break existing cloud-only users |
| Soft | HMAC-SHA256 for UDP auth (hypothesis) |
| Soft | Port 9003 (hypothesis) |

### Unknowns Inventory
- UDP packet format (magic, header layout, checksum) — hypothesis only
- UDP port — hypothesis 9003
- UDP auth token derivation — hypothesis HMAC-SHA256(serial, "fluidra")
- Component IDs 137, 185, 272, 276 — hypothesis backwash/ORP/pH/chlorination
- iQBridge firmware delivery URL — not yet captured

### Risk Assessment
| Risk | Mitigation |
|------|-----------|
| UDP format wrong | Cloud WS fallback always maintained |
| Fluidra API changes | WebSocket stays on; REST as last resort |
| Token derivation wrong | `verify_token_hypothesis()` in local_client.py for live testing |

### Success Criteria
- Local command < 500 ms
- WS update < 2 s
- All sensors accurate vs Fluidra app
- Zero cloud calls in local mode

---

## Phase 2: Task Tree

Tasks decomposed from PRD, priority-ordered:

```
P1 (Core)
├── TASK-001: WebSocket real-time updates        [DONE 2026-03-29]
├── TASK-002: Local UDP client                   [iter-1: stub+packet builder]
├── TASK-003: Dual-mode coordinator              [todo — depends TASK-002]
└── TASK-004: Ghidra RE analysis                 [iter-1: running]

P2 (Enhancement)
├── TASK-005: BUG-001 Smart Auto display fix     [DONE 2026-03-29]
├── TASK-006: BUG-002 Remove deprecated sensor   [DONE 2026-03-29]
├── TASK-007: BUG-003 Error sensor description   [DONE iter-1 2026-03-30]
├── TASK-008: FEAT-001 Chlorinator sensors        [DONE 2026-03-29]
├── TASK-009: FEAT-002 Water temp sensor          [DONE 2026-03-29]
└── TASK-010: Config flow connection_mode         [todo]

P3 (Nice-to-have)
├── TASK-011: FEAT-003 MQTT bridge               [todo]
├── TASK-012: FW-001 Firmware OTA URL            [todo]
├── TASK-013: FW-002 Firmware binary analysis    [todo]
└── TASK-014: FW-003 Custom firmware design      [todo]
```

---

## Phase 3: Ghidra Reverse Engineering

### Binary analyzed
`~/projects/fluidra-re/native/lib/arm64-v8a/libapp.so`
- AARCH64:LE:64:v8A (ARM64)
- 32 MB Dart AOT snapshot
- MD5: 01a42b87ef8872b982602a25d8a7de7e

### Method
1. `apkeep` to download APK (bypasses Cloudflare)
2. Unzip XAPK → extract `libapp.so` from `config.arm64_v8a.apk`
3. `strings libapp.so` — primary analysis (Dart AOT has no C symbols)
4. Ghidra headless import to confirm architecture + get section layout
5. Cipher agent (ollama/huihui_ai/qwen3-abliterated:14b) to interpret strings

### Key findings
- UDP functions confirmed: `initUdpDeviceListener`, `sendUDPCommand`, `udpKey`
- Protocol type: `FluidraMessageProtocol` enum with `MagicNumber` constant
- Auth: `hmac256` + `generateWorkingKey` + `updateUPDkey`
- Checksum: `getCrc32Byte` + `sv4crc`
- Payload: `payloadIntBE` / `payloadIntLE` (big + little endian support)
- BLE OTA: `DevicePropertiesOtaUpdateStatus` tracked via API

### Output
- `docs/RE-libapp.md` — this analysis
- `PROTOCOL_FINDINGS.md` — Cipher session output (packet format hypothesis)
- `PROTOCOL.md` — updated with UDP section

---

## Phase 4: Ralph Loop Execution

### TASK-007 — BUG-003: Error sensor description
| Iter | Act | Evaluate | Commit |
|------|-----|----------|--------|
| 1 | Changed `native_value` to return `"E001 — No water flow detected"` format | All criteria met | `ad9c864` |

**Result:** DONE in 1 iteration.

### TASK-002 — Local UDP client
| Iter | Act | Evaluate | Commit |
|------|-----|----------|--------|
| 1 | Implemented `LocalUDPClient` stub with `_build_packet`, `_hmac_sha256`, `_crc32`, `verify_token_hypothesis` | Packet structure validated (51 bytes), blocked on live capture | `06e6be5` |

**Status:** Blocked — requires `fluidra_debug.py` output with live `commandAndControl.localUdp` JSON.

### TASK-004 — Ghidra analysis
| Iter | Act | Evaluate | Commit |
|------|-----|----------|--------|
| 1 | Ran headless import (AARCH64 confirmed), wrote RE-libapp.md from strings analysis | RE report written, Ghidra analysis in progress | pending |

---

## Phase 5: Dynamic Tasks

Spawned from Ralph loop evaluation:

| Task | Spawned From | Signal | Status |
|------|-------------|--------|--------|
| *(none yet)* | — | — | — |

---

## Phase 6: Session Summary

### Commits this session
| Commit | Task | Description |
|--------|------|-------------|
| `2ad3ab2` | TASK-001/005/006/008/009 | WebSocket, Smart Auto, chlorinator, water temp, RE docs |
| `ad9c864` | TASK-007 iter-1 | Error sensor description fix |
| `06e6be5` | TASK-002 iter-1 | LocalUDPClient stub + packet builder |

### Open blockers
1. **TASK-002** — Needs `fluidra_debug.py` live output → `commandAndControl.localUdp` JSON
2. **TASK-003** — Depends on TASK-002 completing
3. **TASK-004** — Ghidra full analysis still running

### Immediate next action (user)
```bash
cd ~/projects/ha-fluidra-pool
python3 fluidra_debug.py your@email.com yourpassword --ws --zigbee
# Share the output JSON — will unblock TASK-002 + TASK-003
```

---

## Phase 7: CI/CD Improvement Pipeline

> `.github/workflows/improvement.yml` — not yet committed.
> Planned triggers: push to develop, nightly cron.
> Steps: static analysis → test coverage → generate tasks → PR.

---

## Toolchain Used

| Tool | Role |
|------|------|
| `apkeep` | APK download (bypasses Cloudflare) |
| `strings` | Binary string extraction (primary Dart RE method) |
| Ghidra 12.0.4 | Headless import + architecture confirmation |
| Cipher (ollama qwen3-abliterated:14b) | Protocol interpretation from binary strings |
| Claude (council) | Security vulnerability analysis |
| `openclaw agent reverseengineer` | Cipher RE session execution |
| `asyncio.DatagramProtocol` | Non-blocking UDP client |
| `boto3` | AWS Cognito auth (USER_PASSWORD_AUTH) |
| `aiohttp` | REST + WebSocket cloud transport |
