---
id: T05
title: aiohttp Cognito auth with MFA + refresh token (drop boto3)
phase: 2-client
points: 5
status: todo
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
- [ ] Unit tests (aioresponses) cover: login ok; MFA challenge + respond; cached token reused (1 HTTP call for 5 `get_access_token`); refresh used when near expiry; concurrent calls → one login; `NotAuthorizedException` → `FluidraAuthError`; timeout/500 → `FluidraConnectionError`.
- [ ] `grep -rn boto3\|pycognito custom_components/` returns nothing.
- [ ] A test asserts the password/token never appear in captured logs (`caplog`).
- [ ] Full suite passes.

## Out of scope
REST/WS calls (T06). Config-flow MFA UI (T08).
