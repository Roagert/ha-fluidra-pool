---
id: T09
title: Redacted diagnostics download; remove dump_api_data service
phase: 3-core
points: 2
status: done
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
- [x] Test: diagnostics output contains component values but none of the redacted fields' raw values (assert on a fixture that contains fake secrets).
- [x] No `services.yaml`; `hass.services.has_service(DOMAIN, "dump_api_data")` is False.
- [x] Full suite passes.

## Log
- `diagnostics.py`: `{"entry": entry.data, "devices": {id: {"info", "components", "uiconfig"}}}`, all through `async_redact_data`; component 2 `reportedValue`/`desiredValue` → `**REDACTED**`. Keys redacted at any depth: `password, refresh_token, access_token, id_token, token, udpKey, username, email, name, owner, userId, sub, ip, lan_ip, mac, bluetoothMacAddress, ssid`.
- Kept on purpose: device id/`sn`, components 3 (serial) and 7 (Wi-Fi module serial), every other component value and `ts` — reports are useless without them and a serial is not a secret. Entry title/unique_id (they hold the e-mail) are not in the output. Trade-off: `name` is also redacted inside uiconfig (UI labels).
- `dump_api_data` removed (registration in `__init__`, `services.yaml`); strings.json/en.json had no service entries, so they are unchanged. Smoke test asserts the service is gone.
- Test: `tests/test_diagnostics.py` sets up from a mocked cloud serving `tests/fixtures/diagnostics_secrets.json` (a `secret-…` value under every redacted key; asserts the fixture covers `TO_REDACT` and every secret reached the coordinator) and downloads via HA's `/api/diagnostics` endpoint. Mutation-checked: dropping a key, the component-2 step or its `desiredValue`, or adding an uncovered key each fails. 62 passed.
- T16 CHANGELOG: service `fluidra_pool.dump_api_data` removed → use "Download diagnostics". hassfest not run locally.
- Lead review: accepted; lead fix in same commit: keep `name` in uiconfig (component labels needed to map other devices), still redacted in device info/entry.
