---
id: T05
title: aiohttp Cognito auth with MFA + refresh token (drop boto3)
phase: 2-client
points: 5
status: done
depends_on: [T04]
owner: agent
---
## Context
Current `auth.py` uses boto3 (blocking client creation, heavy dep), never uses the
refresh token, and its 10-min refresh threshold vs the ~300 s token TTL means a **full
password login on every check** (≥3 per poll). Every failure (DNS, timeout, throttling)
returns False, which the coordinator turns into `ConfigEntryAuthFailed` → the
integration dies on any network blip (blocker). `ha-fluidra-local/.../cloud_client.py`
lines ~46–135 is a proven plain-JSON Cognito implementation with MFA
(SOFTWARE_TOKEN_MFA and SMS_MFA) — port its logic, not its urllib/thread style.

## Description
Replace `auth.py` with a small async class (target ≤150 lines):
- Uses HA's shared session (`async_get_clientsession(hass)`), 15 s timeout.
- `async_login(username, password)` → tokens, or raises `MfaRequired(session, challenge)`.
- `async_respond_mfa(session, code)` → tokens.
- `async_get_access_token()` → cached token; refreshes via `REFRESH_TOKEN_AUTH` when
  < 30 s left; falls back to password login only if refresh fails *and* no MFA is required;
  guarded by `asyncio.Lock` (no double logins).
- Exceptions: `FluidraAuthError` (NotAuthorized/UserNotFound/expired refresh + MFA) vs
  `FluidraConnectionError` (network, 5xx, throttling). Nothing else escapes.
- Never logs tokens, password, email.
- Remove `boto3`, `pycognito` from `manifest.json` requirements.

## Acceptance criteria
- [x] Unit tests (aioresponses) cover: login ok; MFA challenge + respond; cached token reused (1 HTTP call for 5 `get_access_token`); refresh used when near expiry; concurrent calls → one login; `NotAuthorizedException` → `FluidraAuthError`; timeout/500 → `FluidraConnectionError`.
- [x] `grep -rn boto3\|pycognito custom_components/` returns nothing.
- [x] A test asserts the password/token never appear in captured logs (`caplog`).
- [x] Full suite passes.

## Out of scope
REST/WS calls (T06). Config-flow MFA UI (T08).

## Log
- API (`auth.py`, 139 lines): `FluidraAuth(session, username, password, refresh_token=None)`; `async_login() -> str` (no args: creds live on the instance for the password fallback; raises `MfaRequired(session, challenge)`); `async_respond_mfa(session, code) -> str` (same instance that raised); `async_get_access_token() -> str`; public attr `refresh_token`. `MfaRequired` subclasses `FluidraAuthError`; `FluidraConnectionError` is separate; `COGNITO_URL` exported for tests.
- Call sites: coordinator builds auth on `async_get_clientsession(hass)`; `_async_update_data` maps only `FluidraAuthError` to `ConfigEntryAuthFailed` (connection errors now become `UpdateFailed`); WS loop uses `async_get_access_token()`; `refresh_token_if_needed()` -> `async_get_access_token()` (6x); `get_auth_headers()` -> new coordinator helper `await self._auth_headers()` (11x, same headers as before). config_flow: `async_login()` on the shared session, `MfaRequired` -> error key `mfa_required` (untranslated).
- Tests: `tests/test_auth.py` (15 tests); `mock_auth` fixture removed, `mock_api` now mocks the Cognito POST so the smoke test runs the real auth (1 login per setup). boto3 still installs transitively via HA core (hass-nabucasa -> pycognito).
- T06: wrap REST/WS on `async_get_access_token()`; replace `coordinator._auth_headers()`. T07: drop the coordinator's own `aiohttp.ClientSession()`. T08: MFA step (keep the same `FluidraAuth` instance between steps), `invalid_mfa` = `FluidraAuthError` from `async_respond_mfa`, persist `auth.refresh_token` and pass it to the constructor at setup; connection errors still show `invalid_auth` and `except Exception` still swallows `AbortFlow` (already_configured).
- Lead review: accepted (auth.py read in full; 25 passed). Deviation `async_login()` without args is fine.
