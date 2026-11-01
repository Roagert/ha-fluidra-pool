---
id: T08
title: Config flow — MFA, reauth, compatible unique_id, translations
phase: 3-core
points: 5
status: done
depends_on: [T07]
owner: agent
---
## Context
Current flow: no MFA, no `async_step_reauth` (so reauth crashes with `UnknownStep`),
network errors shown as `invalid_auth`, options flow crashes on current HA
(`self.config_entry = …` AttributeError), translations contain unused steps/entities.
Existing entries: `VERSION = 1`, `unique_id = f"fluidra_pool_{username}"`, data keys
`username, password, device_id, component_id, update_interval, api_rate_limit`.
Reference MFA flow: `ha-fluidra-local/custom_components/fluidra_local/config_flow.py` ~line 177.

## Description
- Steps: `user` (email, password) → optional `mfa` (code) → create entry. Store
  `username`, `password`, `refresh_token`. Errors: `invalid_auth`, `cannot_connect`, `invalid_mfa`, `unknown`.
- `reauth` + `reauth_confirm` (password, then MFA if required) → `async_update_reload_and_abort`.
- Persist rotated refresh token via `hass.config_entries.async_update_entry` when auth reports a new one.
- Remove the options flow (polling interval is not user-tunable anymore — KISS) .
- `async_migrate_entry`: VERSION 1 → 2 drops `device_id, component_id, update_interval,
  api_rate_limit`; keeps unique_id unchanged.
- `strings.json` + `translations/en.json` contain exactly the keys used.

## Acceptance criteria
- [x] Tests: happy path; MFA path; invalid auth; cannot connect; duplicate account aborts `already_configured`; reauth success updates the password and reloads; migration v1→v2 keeps `unique_id` and username/password.
- [x] T07 carry-over: in `tests/test_coordinator.py` the bad-credentials test patches `async_start_reauth`; replace with asserting a `reauth` flow is in `hass.config_entries.flow.async_progress()`.
- [x] Pass the stored `refresh_token` from entry data into `FluidraAuth` in `__init__.py`.
- [x] A v1 entry from the old code loads without user action (test with a v1 `MockConfigEntry`).
- [x] `python -m script.translations`-style check not required; instead a test asserts every `errors`/`abort` key used in code exists in `strings.json`.
- [x] Full suite passes.

## Log
- Flow: `user` (username = e-mail, password) → `mfa` (`code`) when Cognito challenges → entry. `reauth` → `reauth_confirm` (password only: the username is locked to the entry's, so no account-mismatch abort is needed) → `mfa` if asked → `async_update_reload_and_abort` (`reauth_successful`). One `FluidraAuth` per attempt, kept for the MFA step. Errors `invalid_auth`/`invalid_mfa`/`cannot_connect`/`unknown`; `already_configured` aborts before any network call. Deleted: the options flow, 3 unused exception classes in config_flow.py, the scan-interval/rate-limit constants it alone used.
- Entry data v2 = `{username, password, refresh_token}`; `VERSION = 2`; unique_id `fluidra_pool_{username}` and title `Fluidra Pool ({username})` unchanged. `async_migrate_entry` 1→2 keeps username/password only (drops device_id, component_id, update_interval, api_rate_limit); its first setup logs in with the password and stores the refresh token.
- Token: `__init__` passes `entry.data.get("refresh_token")` to `FluidraAuth`; a coordinator listener (also run once after the first refresh) stores `auth.refresh_token` when it changed. There is no update listener, so storing it does not reload. A test asserts the token is not logged.
- Tests: `tests/test_config_flow.py` (11). `translated()` checks every flow result (form fields, errors, abort reason) against strings.json, and every key the code uses is exercised; en.json == strings.json. conftest `config_entry` is now `version=2`. Mutation-checked: removing the token passing, the listener, the migration, `async_step_reauth`, the dup check or a translation each fails a test.
- hassfest not run locally (running a downloaded HA core checkout was denied). strings.json was checked by hand against its `translations.py` rules at 2026.2.3.
- T09: redact `refresh_token`, plus password, username, title and unique_id (which hold the e-mail). T16: README still documents the removed options (update interval, rate limit); CHANGELOG: options flow removed. U03: unverified whether Cognito takes a second code on the same MFA session after a wrong one (the flow re-shows `mfa` with the same session, as ha-fluidra-local does). An MFA account migrated from v1 has no refresh token, so it lands in reauth (password + code).
- Lead review: accepted (config_flow + __init__ read; 61 passed). MFA retry on the same Cognito session after a wrong code is unverified → added to U03.
