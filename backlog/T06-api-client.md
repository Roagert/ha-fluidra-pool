---
id: T06
title: FluidraApi — REST + WebSocket client (the local-ready seam)
phase: 2-client
points: 3
status: done
depends_on: [T05]
owner: agent
---
## Context
REST/WS code is currently spread through a 1,140-line coordinator, with no request
timeouts (default 300 s), duplicated setters, and debug logs that print the bearer token
and full payloads at INFO. The WS URL must carry the token as a query param.
This module is the **seam**: entities/coordinator depend only on these methods, so a
future local transport (T15) implements the same 4 methods.

## Description
New `api.py` (target ≤150 lines), class `FluidraApi(auth, session)`:
- `async_get_devices() -> list[dict]`
- `async_get_components(device_id) -> dict[int, dict]` (keys **int**; value keeps `reportedValue`, `desiredValue`, `ts`)
- `async_get_uiconfig(device_id) -> dict | None` (returns None on 4xx/5xx — device-dependent, issue #4/#5)
- `async_set_component(device_id, component_id: int, value) -> dict`
- `async_listen(device_ids, on_update)` — WS loop: connect `wss://ws.fluidra-emea.com?token=…`,
  subscribe each device, call `on_update(device_id, component_id:int, value, ts)`; reconnect
  with exponential backoff 5 s → 300 s, forever, until cancelled; fresh token per reconnect;
  never logs the URL/token.
- Headers: only `Authorization: Bearer <token>` + `Accept`/`Content-Type: application/json`. Drop the legacy
  `x-api-key`/`x-access-token` (they leak the token into more headers) and the fake `User-Agent` — the confirmed API
  needs none of them. Build on `FluidraAuth.async_get_access_token()` (T05) and replace `coordinator._auth_headers()`.
- 15 s timeout per REST call; 401 → one token refresh + retry; maps errors to
  `FluidraAuthError` / `FluidraConnectionError` from T05.

## Acceptance criteria
- [x] Unit tests: each REST method against aioresponses; PUT body is exactly `{"desiredValue": v}`; 401→refresh→retry once; 500 → `FluidraConnectionError`; uiconfig 500 → None.
- [x] WS test with a fake server (aiohttp test server): subscribe messages sent for each device; a push message calls `on_update` with int component id; dropped connection reconnects; cancel stops cleanly.
- [x] `caplog` test: no token/URL-with-token in logs.
- [x] Not yet wired into the coordinator (T07) — no behaviour change for users.

## Log
- API (`api.py`, 147 lines): `FluidraApi(auth, session)`; `async_get_devices() -> list[dict]`; `async_get_components(device_id) -> dict[int, dict]` (value = the raw component dict); `async_get_uiconfig(device_id) -> dict | None`; `async_set_component(device_id, component_id: int, value) -> dict` (cloud reply, `{}` if empty); `async_listen(device_ids: Iterable[str], on_update) -> None` (runs until cancelled; `on_update(device_id: str, component_id: int, value, ts)` is a sync callback).
- Errors: reuses `FluidraAuthError` (401 again after a fresh token) / `FluidraConnectionError` (other 4xx/5xx, timeout, network, bad JSON); no new exceptions. uiconfig returns None only on HTTP 4xx/5xx (network errors still raise). Auth hook: `FluidraAuth.invalidate_access_token()` drops the cached access token, refresh token kept.
- WS: `ws_connect(WS_URL, params={"token": ...}, heartbeat=30)`, new token per connect, `body` JSON strings merged, unparsable messages ignored at debug; backoff 5→300 s, reset after ≥60 s up; errors logged as type name only (aiohttp errors carry the URL = token). Tests: `tests/test_api.py` (14, local aiohttp server via `aiohttp_server` + `socket_enabled`, `api._sleep` patched).
- T07: devices URL now has `?deviceType=connected` -> update the `mock_api` devices mock (conftest mocks `API_DEVICES_URL` bare); component keys are `int` (coordinator/entities use `str` today); drop `coordinator._auth_headers()` and the WS loop; start `async_listen(self.devices, ...)` with `entry.async_create_background_task` (dict keys are re-read per reconnect) so the smoke-test `_start_websocket` patch can go; map `FluidraAuthError` -> `ConfigEntryAuthFailed`, `FluidraConnectionError` -> `UpdateFailed`.
- Lead review: accepted (api.py read in full; 39 passed).
