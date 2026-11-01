# PRD — ha-fluidra-pool

**Version 3.0** · 2026-11-01 · Release 2.0.0 · Supersedes v2.0 (which assumed local UDP for the heat pump)

## Goal

One simple, correct Home Assistant integration (`fluidra_pool`) for Fluidra connected
devices, heat pump first. **Local-ready**: cloud REST + WebSocket push today, behind one
small client (`FluidraApi`) that a proven local transport can replace without touching
entities.

## Users and devices

Owners of a Fluidra cloud account (EMEA). Tested: Amitime inverter heat pump (`amt`).
Other devices (#3 #4 #5 #8) must set up without errors and never show guessed values; they
get proper entities only once owners send diagnostics.

## Requirements (2.0.0)

1. **Login**: e-mail + password, MFA code when Cognito asks, reauth when the login is
   rejected. Plain aiohttp (no boto3); refresh token stored; network errors retry and never
   force a reauth.
2. **Data**: all devices, REST poll every 5 min + WebSocket push; never blocks HA startup (#9).
3. **Heat pump**: climate (off/heat/cool/auto × smart/boost/silence, 15–40 °C, hvac_action),
   power switch, water/air/target temperature, Wi-Fi signal, no-flow sensor.
4. **Every device**: error information; others: component count + raw component sensors.
5. **Diagnostics** download with secrets and home-network identity redacted.
6. **Compatibility**: domain, entry unique id `fluidra_pool_<username>`, device identifiers
   and the unique ids of climate / water temperature / error information unchanged; every
   removed entity listed in `CHANGELOG.md`.

Non-goals: options, services, guessed mappings, BLE, non-EMEA clouds, custom firmware,
MQTT bridge.

## Constraints (established facts)

- Access token lives about 300 s → refresh 30 s before expiry, never a password login per call.
- WebSocket auth is the token in the query string; push format is unverified.
- UI config returns HTTP 500 for some devices → optional.
- The `amt` pump talks to AWS IoT only: no `commandAndControl.localUdp`, no open LAN ports,
  no UDP replies, no SSDP, no BLE advert. Protocol: `PROTOCOL.md`.

## Local control (gated)

Research by access-point packet capture only (`docs/LOCAL_CAPTURE.md`). Decision record
`docs/LOCAL_DECISION.md` (T14): if the phone talks to the pump on the LAN during a setpoint
change, implement that transport behind `FluidraApi` (T15); otherwise stay cloud-push.
`local_client.py` (iQBridge RS UDP hypothesis) stays unwired.

## Success criteria

- Live test on the maintainer's HA (U03): setup incl. MFA, values match the app, commands
  apply, pushes arrive, restart without reauth.
- CI green (pytest, hassfest, HACS). Issues #1 #2 #9 fixed.

## Open questions

WebSocket push format; meaning of components 11 (running) and 28 (no flow); 42 °C maximum
via UI config; format of the cloud's `alarms` list; component maps of other devices.
