---
id: T12
title: Other devices — no crash, no bogus values, generic sensors
phase: 4-entities
points: 5
status: todo
depends_on: [T11]
owner: agent
---
## Context
Issues from users we can't test:
- #5 Tecno LC2 / Zodiac IQ 12: "Component 13 NOT FOUND", uiconfig 500, sensors unknown.
- #4 Blue Connect Gold: uiconfig 500; water temp shows 404.2 °C (wrong scaling/sentinel).
- #8 Ei2q Evo: pH/pH-setpoint stuck at 2.54 (raw 254 = probable "no data" sentinel), ORP mixes with setpoint, temp/salinity 0.0.
- #3 Irripool iSalt: only generic entities.
Thomas chose: graceful handling + diagnostics (T09) + generic sensors; proper mapping
only after reporters share diagnostics.

## Description
- Heat-pump entities only for devices that have components 13, 14, 15 and 19.
- For every other device: create a **disabled-by-default** generic numeric sensor per
  component listed in uiconfig with a recognisable unit (when uiconfig is available), else none;
  always create a `component_count` diagnostic sensor so the device appears with useful info.
- Value sanity guard (one small function): temperatures outside −30…80 °C → unavailable;
  pH outside 0…14 → unavailable; raw 254/255/65535 sentinels → unavailable.
- No exceptions anywhere when components/uiconfig are missing (log once at debug).
- `backlog/ISSUE_REPLIES.md`: draft (not post) a short reply per issue #3 #4 #5 #8 asking
  for the diagnostics download from the new release.

## Acceptance criteria
- [ ] Tests with fixtures `components_chlorinator.json` (incl. 254 pH), `components_blueconnect.json` (incl. 4042 temp), `components_no13.json`: setup succeeds, no climate entity, sentinel/out-of-range → unavailable, no error logs.
- [ ] uiconfig 500 → setup still succeeds (test).
- [ ] `ISSUE_REPLIES.md` exists with 4 drafts.
- [ ] Full suite passes.
