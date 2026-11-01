---
id: T07
title: Rewrite coordinator (1,140 → ~200 lines), fix startup block #9
phase: 3-core
points: 8
status: todo
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

## Acceptance criteria
- [ ] Test: setup with WS mocked never blocks — `hass.async_block_till_done()` returns while the listener runs (regression test for #9).
- [ ] Test: API down at boot → entry state `SETUP_RETRY`; bad creds → `SETUP_ERROR` + reauth flow started.
- [ ] Test: poll failure → entities unavailable; recovery → available.
- [ ] Test: WS update with older `ts` is ignored; newer is applied.
- [ ] Test: two devices on account → both in `coordinator.data`.
- [ ] Unload cancels WS task and leaves no pending tasks (pytest-hacc `expected_lingering_tasks` false).
- [ ] `wc -l coordinator.py` ≤ 250. Full suite passes.
