---
id: U02
title: Run the 3-minute AP capture
phase: 5-local
points: 2
status: todo
depends_on: [T13]
owner: user
---
## Steps for Thomas
Follow `docs/LOCAL_CAPTURE.md`. Either run it yourself and paste the
`analyze_capture.py` output, or give the lead temporary UniFi device SSH credentials
(revoke afterwards).

## Acceptance criteria
- [ ] Analyzer output for a capture that includes the setpoint +1 °C / restore events.
