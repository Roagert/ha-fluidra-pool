# Product Requirements Document — ha-fluidra-pool
**Version:** 2.0 | **Date:** 2026-03-30 | **Status:** Active

---

## 1. Objective

Build a production-quality Home Assistant custom integration for Fluidra iQBridge pool heat pump controllers that operates **primarily via local LAN** (zero cloud dependency for command/status), with cloud WebSocket as fallback and cloud REST as last resort — while also documenting the full reverse-engineered protocol for open-source community use.

---

## 2. Scope

### In Scope
- Local UDP client (direct LAN control, <100 ms latency)
- Cloud WebSocket client (real-time push, <2 s latency)
- Cloud REST polling fallback (15-min interval)
- HA climate entity (heat/cool/auto/off + Smart Auto preset)
- HA sensor entities: water temp, setpoint, mode, power, error, pH, ORP, salinity, chlorine
- HA button entities: manual refresh
- Config flow with connection mode selection
- Full reverse-engineering documentation (PROTOCOL.md, PROTOCOL_FINDINGS.md)
- Security research findings

### Out of Scope
- Custom iQBridge firmware (long-term FW-001/002/003, not this PRD cycle)
- MQTT bridge (FEAT-003, future)
- Mobile app replacement
- BLE direct control (requires iQBridge RS physical proximity)
- Support for non-EMEA Fluidra regions

---

## 3. Stakeholders

| Role | Responsibility |
|------|---------------|
| @Roagert | Device owner, integration maintainer |
| HA Community | End users of the integration |
| Cipher (RE agent) | Protocol reverse engineering |

---

## 4. Functional Requirements

### FR-01: Local UDP Control
**Description:** When iQBridge RS is on the same LAN, use local UDP for all commands and status reads. Zero internet traffic for device control.
**Acceptance Criteria:**
- [ ] Coordinator detects `commandAndControl.localUdp` from cloud API on startup
- [ ] UDP client sends correctly formatted packets to iQBridge
- [ ] Commands execute in < 500 ms
- [ ] Falls back to WebSocket if UDP unavailable

### FR-02: WebSocket Real-Time Updates
**Description:** Maintain persistent WebSocket connection to `wss://ws.fluidra-emea.com` for push state updates.
**Acceptance Criteria:**
- [x] WS connects on coordinator start *(implemented 2026-03-29)*
- [x] Subscribes to all device IDs on connect
- [x] WS events update coordinator state immediately
- [x] Auto-reconnects with exponential backoff

### FR-03: Climate Entity
**Description:** HA climate entity with correct mode mapping.
**Acceptance Criteria:**
- [x] Smart Auto shows as `HVACMode.AUTO` *(fixed 2026-03-29)*
- [x] Setting `hvac_mode=auto` activates Smart Auto (component 14=2)
- [ ] `hvac_action` shows heating/cooling/idle correctly
- [ ] Setpoint changes via `set_temperature` service

### FR-04: Sensor Entities
**Acceptance Criteria:**
- [x] Water temperature (component 19, °C) *(added 2026-03-29)*
- [x] pH, ORP, salinity, free chlorine (chlorinator) *(added 2026-03-29)*
- [ ] Diagnostic error sensor shows error code + message (BUG-003)
- [ ] All sensors update within 2 s via WebSocket

### FR-05: Config Flow
**Description:** User-facing setup with connection mode selection.
**Acceptance Criteria:**
- [ ] `connection_mode`: auto / cloud_only / local_only
- [ ] Existing cloud-only users unaffected by default (`auto`)
- [ ] Validates credentials on setup

---

## 5. Non-Functional Requirements

| NFR | Requirement | Measure |
|-----|------------|---------|
| Latency | Local mode command latency | < 500 ms |
| Latency | WebSocket state update | < 2 s |
| Reliability | Auto-reconnect WS after failure | Within 30 s |
| Security | Local UDP token not hardcoded | Derived per-device |
| Compatibility | HA version | 2024.1+ |
| API Rate Limit | Cloud REST calls | ≤ 60/min |

---

## 6. Technical Architecture

- **Language:** Python 3.11+
- **HA Framework:** DataUpdateCoordinator pattern
- **Auth:** AWS Cognito USER_PASSWORD_AUTH (eu-west-1)
- **Cloud transport:** aiohttp (REST + WebSocket)
- **Local transport:** asyncio DatagramProtocol (UDP)
- **Config:** config_flow.py → HA config entries

```
HA Core
  └─ FluidraCoordinator
       ├─ [primary]  LocalUDPClient ──► iQBridge LAN
       ├─ [fallback] CloudWSClient  ──► wss://ws.fluidra-emea.com
       └─ [poll]     CloudRESTClient ──► api.fluidra-emea.com
```

---

## 7. Constraints & Assumptions

- iQBridge RS required for local UDP (iQBridge ZB uses Zigbee, different path)
- `commandAndControl.localUdp` field must be present in API response for local mode
- UDP packet format is hypothesis until live traffic capture confirms it
- Cognito tokens expire after 1 hour; refresh token valid 30 days

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| UDP packet format wrong (hypothesis) | Medium | HIGH | `fluidra_debug.py --ws` live capture; tcpdump |
| Fluidra changes cloud API | Low | HIGH | WebSocket fallback always maintained |
| Cognito token rate limiting | Low | MEDIUM | Token refresh only when < 10 min to expiry |
| UDP auth token prediction (security) | Medium | HIGH | Report via responsible disclosure |
| iQBridge firmware update breaks local mode | Low | MEDIUM | Cloud fallback always maintained |

---

## 9. Success Criteria

- [ ] Local UDP: command round-trip < 500 ms on LAN
- [ ] WebSocket: state update < 2 s after pool event
- [ ] All sensors show correct values matching Fluidra app
- [ ] Integration survives HA restart without re-authentication
- [ ] Zero cloud calls for device control in local mode
- [ ] Protocol documented such that a new developer can implement a client from scratch

---

## 10. Open Questions

- UDP packet format: magic bytes, checksum type, auth placement — needs `tcpdump` capture
- UDP port: hypothesis 9003, unconfirmed
- UDP auth token: hypothesis HMAC-SHA256(serial, "fluidra"), unconfirmed
- Component IDs 137, 185, 272, 276: hypothesis backwash/ORP/pH/chlorination, needs uiconfig verification
- iQBridge ZB local control: Zigbee path entirely separate — out of scope for now
