---
id: U03
title: Live test on Thomas's Home Assistant + release
phase: 6-release
points: 2
status: todo
depends_on: [T18]
owner: user
---
## Steps for Thomas
1. Install branch `finalize-v1` via HACS (custom repo, branch) or copy `custom_components/fluidra_pool`.
2. Check: HA starts in normal time; climate shows the right mode; HEAT/COOL/AUTO/OFF and
   setpoint work from HA and appear in the Fluidra app within ~5 s; app changes show in HA within ~5 s (WebSocket);
   unplug internet → entities go unavailable, come back after.
3. If your account has MFA: add the integration, enter a **wrong** code once, then the right one — it must succeed (if it fails, report it: the flow then needs a fresh login per retry).
4. Download diagnostics and confirm no secrets in it.
5. Approve merge + tag `v2.0.0`.

## Acceptance criteria
- [ ] Thomas confirms all checks; release tagged.
