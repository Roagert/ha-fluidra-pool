---
id: T09
title: Redacted diagnostics download; remove dump_api_data service
phase: 3-core
points: 2
status: todo
depends_on: [T08]
owner: agent
---
## Context
`dump_api_data` logs email/name/full payloads at INFO and is never unregistered.
Owners of other devices (issues #3 #4 #5 #8) need a safe way to send us their data.

## Description
- `diagnostics.py` → `async_get_config_entry_diagnostics` returning, per device: info,
  components, uiconfig (if any). Use `async_redact_data` for: `password, refresh_token,
  access_token, id_token, username, email, name, sub, ip, lan_ip, mac, ssid, token, udpKey`
  and component **2** (LAN IP) value.
- Delete `services.yaml` and the `dump_api_data` service registration.

## Acceptance criteria
- [ ] Test: diagnostics output contains component values but none of the redacted fields' raw values (assert on a fixture that contains fake secrets).
- [ ] No `services.yaml`; `hass.services.has_service(DOMAIN, "dump_api_data")` is False.
- [ ] Full suite passes.
