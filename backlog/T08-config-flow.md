---
id: T08
title: Config flow — MFA, reauth, compatible unique_id, translations
phase: 3-core
points: 5
status: todo
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
- [ ] Tests: happy path; MFA path; invalid auth; cannot connect; duplicate account aborts `already_configured`; reauth success updates the password and reloads; migration v1→v2 keeps `unique_id` and username/password.
- [ ] A v1 entry from the old code loads without user action (test with a v1 `MockConfigEntry`).
- [ ] `python -m script.translations`-style check not required; instead a test asserts every `errors`/`abort` key used in code exists in `strings.json`.
- [ ] Full suite passes.
