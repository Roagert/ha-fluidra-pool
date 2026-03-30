---
id: TASK-DYN-001
title: Recover Fluidra credentials and re-run fluidra_debug.py
priority: P0
status: todo
depends_on: []
branch: task/TASK-DYN-001-recover-credentials
iteration: 0
max_iterations: 3
created: 2026-03-30
spawned_from: TASK-002 iteration 2
signal: "[AUTH FAILED] NotAuthorizedException: Incorrect username or password."
---

## Description

`fluidra_debug.py` authentication failed with credentials `thomasroager@gmail.com` / `S0davand`.
The password may have changed or account may use 2FA. This blocks TASK-002 (local UDP client)
because we need the live `commandAndControl.localUdp` JSON to get the confirmed UDP host, port,
and token for iQBridge RS.

## Acceptance Criteria
- [ ] `fluidra_debug.py` runs successfully and saves output JSON
- [ ] `commandAndControl.localUdp` object extracted from output
- [ ] UDP host, port, and token confirmed or refuted vs hypothesis

## User Action Required

The user needs to:
1. Check current Fluidra app credentials (may have changed)
2. Run: `python3 fluidra_debug.py <email> <password> --ws --zigbee`
3. Share the output JSON or at least the `commandAndControl` section

## Implementation Notes

Once credentials work, the debug script will produce:
- `fluidra_debug_<timestamp>.json` — full API dump
- `fluidra_debug_<timestamp>.txt` — human-readable summary

Key field to extract:
```json
{
  "commandAndControl": {
    "localUdp": {
      "host": "<LAN IP>",
      "port": <port>,
      "token": "<auth token>"
    }
  }
}
```

Then compare token against `verify_token_hypothesis(serial)` candidates in `local_client.py`.
