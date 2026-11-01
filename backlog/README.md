# ha-fluidra-pool — Finalization Backlog

One file per task (`T*.md` = agent work, `U*.md` = needs Thomas). Progress:
`python3 backlog/progress.py` (also regenerates `backlog/PROGRESS.md`).

## Goal

Ship **one** simple, correct Home Assistant integration (`fluidra_pool`) for Fluidra
connected devices, heat pump first, that is *local-ready*: cloud REST + WebSocket push
today, with a tiny client seam so a proven local transport can plug in later without
touching entities.

## Decisions (made 2026-11-01 by Thomas)

1. **Base = this repo** (`fluidra_pool` domain). Port the good parts of
   `Roagert/ha-fluidra-local` (aiohttp Cognito login with MFA, switch, binary sensor,
   device picker, tests). Deprecate `ha-fluidra-local` and `fluidra-local-addon` at the end.
2. **Secrets**: rewrite git history to purge them, force-push `main` and the PR #7 branch.
3. **Local path**: research via **AP packet capture** only (UniFi AP 192.168.1.55).
4. **Other devices** (issues #3 #4 #5 #8): don't crash, no bogus values, redacted
   diagnostics, generic sensors; proper mapping only once reporters send diagnostics.

## Established facts (do not re-derive)

- Thomas's device: Amitime heat pump, type `amt`, id/serial `LG24440781`, fw 2.5.0,
  ESP32 Wi-Fi (MAC ac:15:18:98:15:f0) at `192.168.1.29`. Talks to the cloud via AWS IoT.
- LAN scans: no open TCP ports 1–65535, no reply to UDP probes (incl. 9003/8902), no
  SSDP, no BLE advert in normal mode. Cloud payload has **no** `commandAndControl.localUdp`.
  `local_client.py` is an unwired stub for iQBridge RS — not applicable to `amt`.
- Auth: AWS Cognito `eu-west-1`, pool `eu-west-1_OnopMZF9X`, client `g3njunelkcbtefosqm9bdhhq1`,
  `USER_PASSWORD_AUTH` (+ MFA challenge for some accounts), **access-token TTL ≈ 300 s**.
  Cognito JSON API = plain HTTPS POST to `https://cognito-idp.eu-west-1.amazonaws.com/`
  with `X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth` — no boto3 needed.
  Working reference implementation: `ha-fluidra-local/custom_components/fluidra_local/cloud_client.py`.
- REST base `https://api.fluidra-emea.com`, header `Authorization: Bearer <access>`:
  - `GET /generic/devices?deviceType=connected`
  - `GET /generic/devices/{id}/components?deviceType=connected` → list of `{id, reportedValue, desiredValue?, ts}`
  - `GET /generic/devices/{id}/uiconfig?appId=iaq&deviceType=connected` (returns 500 for some devices)
  - `PUT /generic/devices/{id}/components/{cid}?deviceType=connected` body `{"desiredValue": v}`
- WebSocket: `wss://ws.fluidra-emea.com?token=<access>` (token in **query**, not header).
  Subscribe `{"action":"subsDevice","deviceType":"connected","deviceId":"<id>"}`.
  Push format (unverified): `{"action":"command","deviceId":..,"componentId":"13","reportedValue":1}`.
- Heat-pump components: 13 power (0/1) · 14 mode (0 SmartHeat, 1 SmartCool, 2 SmartAuto,
  3 BoostHeat, 4 SilenceHeat, 5 BoostCool, 6 SilenceCool) · 15 setpoint °C×10 (150–420) ·
  19 water temp °C×10 · 62 air temp °C×10 · 11 running state (0 idle/1 running, **unverified**) ·
  1 Wi-Fi RSSI · 2 LAN IP · 3 serial · 4 firmware · 28 no-flow error (per ha-fluidra-local, verify).

## Compatibility invariants (existing users must not lose entities)

- Domain `fluidra_pool`; config entry `unique_id = f"fluidra_pool_{username}"`; entry data keys
  `username`, `password` stay readable (add a migration if the schema changes).
- Device identifiers `(DOMAIN, device_id)`.
- Entity unique IDs kept: `fluidra_{device_id}_climate_heatpump`,
  `fluidra_{device_id}_water_temperature`, `fluidra_{device_id}_error_information`.
  Removed entities are listed in `CHANGELOG.md` as breaking changes.

## Rules for every task (Karpathy guidelines — see `/CLAUDE.md`)

1. Think first: state assumptions; if the task file is ambiguous, stop and report.
2. Simplicity: minimum code; no speculative options/abstractions; delete > add.
3. Surgical: touch only files the task names; mention (don't fix) unrelated problems.
4. Goal-driven: write/adjust the test first, make it pass, run the full suite.
5. Never log, print, commit or echo secrets (password, tokens, refresh token, email).
6. Work on branch `finalize-v1` in `/home/user/ha-fluidra-pool`; one commit per task,
   message `T<NN>: <title>`; do **not** push (the lead verifies, then pushes).
7. Finish by setting `status: done` in the task file's front matter and ticking the
   acceptance boxes you actually verified — leave unverified boxes unticked and say why.

## Order

T01 → U01 → T02 → T03 → T04 → **T13** (early, so Thomas can do U02 in parallel) →
T05 → T06 → T07 → T08 → T09 → T10 → T11 → T12 → T14 (after U02) → T15 → T16 → T17 →
T18 → U03.

## How a task is executed

The lead spawns **one fresh subagent per task**, sequentially. The prompt is this README
+ the task file + `/CLAUDE.md`. The subagent implements, tests, commits locally and
reports. The lead checks every acceptance box against the diff and the test run, pushes, then
updates the task status and `PROGRESS.md`.
