---
id: T16
title: Manifest, README, PROTOCOL, PRD v3, CHANGELOG
phase: 6-release
points: 3
status: todo
depends_on: [T12]
owner: agent
---
## Context
`manifest.json` has invalid keys (brand, model, supported_by, icon, logo, homeassistant,
ssdp/zeroconf/homekit empty), a false `quality_scale: platinum`, wrong `iot_class`
(`cloud_polling` → `cloud_push`), no `loggers`, `aiohttp` listed. HA min version must be
≥ 2024.2 (`ClimateEntityFeature.TURN_ON`). Docs are stale: PRD says tokens last 1 h
(really ~300 s) and assumes UDP-local for `amt`; `PROTOCOL_FINDINGS.md` lists the old
LAN IP `.11` (now `.29`); `PROTOCOL.md` describes the wrong WS auth; README describes
features that no longer exist.

## Description
- `manifest.json`: domain, name, codeowners, config_flow, documentation, issue_tracker,
  integration_type `hub`, iot_class `cloud_push`, loggers `["custom_components.fluidra_pool"]`,
  requirements `[]`, version `2.0.0`. `hacs.json`: `homeassistant: "2024.2.0"`.
- `README.md`: what it is, supported devices (tested: Amitime heat pump; others: generic),
  install (HACS), setup (MFA), entities table, local-control status (link LOCAL_DECISION if present), diagnostics how-to.
- Merge `PROTOCOL_FINDINGS.md` into `PROTOCOL.md` (one protocol doc, no PII), fix WS auth/IP.
- `docs/PRD.md` v3 reflecting decisions in `backlog/README.md`.
- `CHANGELOG.md` 2.0.0: breaking changes (removed entities from T11 log, options removed), fixes (#1 #2 #9), new (MFA, reauth, diagnostics, switch, binary sensor).
- Delete stale `docs/AUTONOMOUS_ENGINEER_FLOW.md` and `custom_components/fluidra_pool/icon.svg|logo.png` if HACS brand assets are handled via `brands` repo — else keep (decide, note why).

## Acceptance criteria
- [ ] CI hassfest + HACS jobs pass (run locally via `docker run` if available, else note).
- [ ] `grep -rn "192.168.1.11\|Authorization: Bearer.*ws\|USER_SRP" *.md docs/` → nothing stale.
- [ ] No PII (email, name, pool id) in any doc.
