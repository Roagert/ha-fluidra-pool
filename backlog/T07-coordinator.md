---
id: T07
title: Rewrite coordinator (1,140 → ~200 lines), fix startup block #9
phase: 3-core
points: 8
status: done
depends_on: [T06]
owner: agent
---
## Context
Review findings in `coordinator.py`:
- WS listener started with `hass.async_create_task` → HA startup blocked ~5 min (issue #9;
  tested fix in external PR #10 by @kifeo — credit with `Co-authored-by: kifeo <20202649+kifeo@users.noreply.github.com>`).
- Every `_fetch_*` swallows all exceptions, so `UpdateFailed` never fires and entities
  stay "available" with stale data; setup returns False instead of `ConfigEntryNotReady`.
- Poll results overwrite newer WS values (no `ts` check); WS stores int keys, REST str keys.
- Still polls deprecated `/mobile/consumers/me`, user profile, pools, pool status every poll.
- Only the first device on the account is used.

## Description
Rewrite `coordinator.py` + `__init__.py` around `FluidraApi` (T06):
- `async_setup_entry`: build auth+api from entry data; first refresh; on
  `FluidraConnectionError` → `ConfigEntryNotReady`; on `FluidraAuthError` → `ConfigEntryAuthFailed`.
  Store runtime objects in `entry.runtime_data`.
- Coordinator data: `{device_id: {"info": device_dict, "components": {int: {...}}}}` for
  **all** devices on the account; uiconfig fetched once at setup (None tolerated).
- Poll every 5 min (WS provides freshness); errors → `UpdateFailed`.
- WS via `entry.async_create_background_task(hass, api.async_listen(...), "fluidra_pool_ws")`
  (auto-cancelled on unload). WS updates merge only if `ts` ≥ stored `ts`, then
  `async_set_updated_data`.
- `async_set_component(device_id, cid, value)`: PUT, optimistic local merge, then refresh
  shortly after; raise `HomeAssistantError` on failure.
- Delete: rate limiter, retry wrapper, consumer/profile/pools/pool-status fetches,
  unused getters, `local_client.py` import paths (leave `local_client.py` deletion to T15
  decision — just ensure nothing imports it).
- Keep `dump_api_data` service working until T09 replaces it, or remove it there.
- Remove the `_start_websocket` patch from `tests/test_smoke.py` (added in T04) and make the smoke test pass without it.

## Acceptance criteria
- [x] Test: setup with WS mocked never blocks — `hass.async_block_till_done()` returns while the listener runs (regression test for #9).
- [ ] Test: API down at boot → entry state `SETUP_RETRY`; bad creds → `SETUP_ERROR` + reauth flow started.
- [x] Test: poll failure → entities unavailable; recovery → available.
- [x] Test: WS update with older `ts` is ignored; newer is applied.
- [x] Test: two devices on account → both in `coordinator.data`.
- [x] Unload cancels WS task and leaves no pending tasks (pytest-hacc `expected_lingering_tasks` false).
- [x] `wc -l coordinator.py` ≤ 250. Full suite passes.

## Log
- API: `FluidraPoolDataUpdateCoordinator(hass, entry, api)` = `entry.runtime_data`; `.api`; `.data = {device_id: {"info": raw device dict, "components": {int: {"id", "reportedValue", "desiredValue"?, "ts"}}}}` (all devices); `.uiconfig = {device_id: dict | None}` (once per device, first poll); `async_set_component(device_id, cid: int, value)` (PUT → optimistic `reportedValue`, ts kept → refresh 1 s later via a non-immediate debouncer; `HomeAssistantError` on failure); `@callback async_handle_push(device_id, cid, value, ts)`. Poll 5 min; `FluidraAuthError`→`ConfigEntryAuthFailed`, `FluidraConnectionError`→`UpdateFailed`. Poll and push both keep the newer `ts`.
- WS: `entry.async_create_background_task(hass, api.async_listen(list(coordinator.data), coordinator.async_handle_push), "fluidra_pool_ws")` — devices found at setup only. Tests: `mock_ws` (FakeWebSocket patching `aiohttp.ClientSession.ws_connect`; `.push(**event)`, `.subscribed`, `.closed`), `config_entry`, `cloud_devices` (parametrizable). #9 test checked by mutation: `hass.async_create_task` → `TimeoutError`.
- Shim (`# --- compat shim` blocks, delete in T10/T11): coordinator `consumer_data`, `user_profile_data`, `pool_status_data`, `user_pools_data` (all `{}`), `device_id` (first heat pump {13,14,15,19}, else first), `devices` (via `_legacy_device`/`_alarm_text`; `{}` after a failed poll → old entities unavailable), `device_components_data`, `device_uiconfig_data`, `error_information`, `set_component_value`/`set_power_value`/`set_temperature_value`, `schedule_quick_update` (no-op); `__init__`: `hass.data[DOMAIN][entry_id]` (+ pop on unload) and "no devices → return False".
- Removed behaviour (old code deleted): sensors `user_profile_data`, `user_pools_data` (unique-id suffixes, for CHANGELOG) gone with their fetches; error sensor attr `timestamp` now None; UI-config sensor keyed by real device id; failed commands raise instead of only logging; refresh button refreshes 1 s after press; poll fixed 5 min (options `update_interval`/`api_rate_limit` ignored, reload-on-update listener dropped); `_setup_device_registry` dropped (entities register the same device — old/new states + registry diffed: otherwise identical).
- Reauth box left open: SETUP_RETRY/SETUP_ERROR and `ConfigEntry.async_start_reauth` call are tested, but the reauth flow itself dies with `UnknownStep` until T08 adds `async_step_reauth` (test patches `async_start_reauth`; T08: assert the flow in `flow.async_progress()` instead).
- T08: options flow is now a no-op; no update listener, so persisting a refresh token won't reload. T09: `dump_api_data` kept (4 lines in `__init__`, logs `data`+`uiconfig` at INFO) → replace, delete `services.yaml`. T10/T11: use `runtime_data`/`data`/`async_set_component`, grep "compat shim". T12: an HTTP error for any one device fails the whole poll; uiconfig 500 → None is fine. Push callback exceptions (e.g. non-numeric `ts`) end the listener task — verify the push format in U03.
- Lead review: accepted (coordinator + __init__ read; 46 passed). Reauth box stays unticked → moved to T08.
  Lead fix in the same commit: `api._parse_push` coerces `ts` to float seconds (ms → s; bad ts →
  message ignored) so an unverified push format can neither outrank polls forever nor kill the listener.
