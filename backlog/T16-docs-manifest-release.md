---
id: T16
title: Manifest, README, PROTOCOL, PRD v3, CHANGELOG
phase: 6-release
points: 3
status: in_progress
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
- Note: invalid manifest keys and `aiohttp` were already removed by the lead to unblock CI hassfest (commit `CI: …`).
- `manifest.json`: domain, name, codeowners, config_flow, documentation, issue_tracker,
  integration_type `hub`, iot_class `cloud_push`, loggers `["custom_components.fluidra_pool"]`,
  requirements `[]`, version `2.0.0`. `hacs.json`: `homeassistant: "2025.2.0"` (code uses `AddConfigEntryEntitiesCallback` (2025.2) and `DeviceInfo.model_id` (2024.8) — verify against HA release notes).
- `README.md`: what it is, supported devices (tested: Amitime heat pump; others: generic),
  install (HACS), setup (MFA), entities table, local-control status (link LOCAL_DECISION if present), diagnostics how-to.
- Merge `PROTOCOL_FINDINGS.md` into `PROTOCOL.md` (one protocol doc, no PII), fix WS auth/IP.
- `docs/PRD.md` v3 reflecting decisions in `backlog/README.md`.
- `CHANGELOG.md` 2.0.0: breaking changes (removed entities from T11 log, options removed), fixes (#1 #2 #9), new (MFA, reauth, diagnostics, switch, binary sensor).
- Root `README.md` contains unresolved merge-conflict markers (lines 1/68/305) — the rewrite replaces it.
- Delete `scripts/ghidra_*.py` (RE tooling; belongs in `Roagert/fluidra-re`) and stale `docs/AUTONOMOUS_ENGINEER_FLOW.md` and `custom_components/fluidra_pool/icon.svg|logo.png` if HACS brand assets are handled via `brands` repo — else keep (decide, note why).

## Acceptance criteria
- [ ] CI hassfest + HACS jobs pass (run locally via `docker run` if available, else note).
- [x] `grep -rn "192.168.1.11\|Authorization: Bearer.*ws\|USER_SRP" *.md docs/` → nothing stale.
- [x] No PII (email, name, pool id) in any doc.
- [x] `grep -rn '^<<<<<<<\|^>>>>>>>' .` → nothing.

## Log
- HA minimum **2025.3.0**, not 2025.2.0: HA core source at release tags (raw.githubusercontent) has no `AddConfigEntryEntitiesCallback` in `entity_platform.py` at 2025.2.5, defines it at 2025.3.0; `DeviceInfo.model_id` from 2024.8, `_get_reauth_entry` and `DataUpdateCoordinator(config_entry=)` from 2024.11, `runtime_data`/`async_create_background_task`/`async_update_reload_and_abort(data=)` older. Dev blog not reachable (host blocked).
- CI box open: hassfest/HACS not run (no docker daemon). Instead read hassfest `manifest.py`/`util.py` @2026.2.3 (schema + sort rule, order checked by script) and HACS validators: brands passes via `home-assistant/brands` `custom_integrations/fluidra_pool/icon.png`; `images` check is plugin/theme only. Dropped `dependencies: []` too.
- Deleted: PROTOCOL_FINDINGS.md (merged), scripts/ghidra_*.py, docs/AUTONOMOUS_ENGINEER_FLOW.md, docs/usage.md + troubleshooting.md (README covers it in less text), icon.svg/logo.png (HA never reads them; the brand comes from the brands repo; HA 2026.3 local brands would need `brand/*.png`). References fixed: 3 code comments + docs/RE-libapp.md → PROTOCOL.md.
- PROTOCOL.md: dropped device id/serials, LAN IP, redacted markers, boto3/nmap/curl snippets, task tables; live mode table; WS token in query; Cognito MFA/refresh. CHANGELOG from T05–T12 logs, plus `climate_heatpump` on non-heat-pumps (1.x created it for the configured device of any type).
- Not touched: docs/LOCAL_CAPTURE.md still holds home LAN IPs and the pump MAC (U02 runbook; outside the PII criterion) — redact after U02. 138 passed.
