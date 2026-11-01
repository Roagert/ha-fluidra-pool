---
id: T14
title: Analyze capture → local-path decision record
phase: 5-local
points: 3
status: todo
depends_on: [U02]
owner: agent
---
## Context
Decision gate for local control. Possible outcomes:
A) phone↔heatpump LAN traffic during the setpoint change → a local protocol exists (UDP/TCP) → T15 implements it.
B) heat pump only talks TLS to AWS IoT / Fluidra hosts (MQTT 8883 or 443), nothing on LAN →
   stock firmware has no local API; T15 is re-scoped to "document + options".
C) inconclusive (capture missed the window) → repeat U02 once.

Prior evidence (PR #7 branch, `docs/fluidra-unifi-ap-capture-20260517.md`): a 120 s `br0`
capture on the UniFi AP during two cloud setpoint writes (pump powered off) saw only ARP
(gratuitous ARP every 60 s) and a TCP RST from port 80 — no DNS, no TLS, no cloud traffic.
So either the pump was offline from the cloud, or its traffic took another AP interface/VLAN.
U02 now captures on `-i any` and power-cycles the pump to force DHCP → DNS → TLS.

## Description
Write `docs/LOCAL_DECISION.md`: evidence table (from analyzer output), outcome A/B/C,
and for B the realistic options with effort/risk: (1) stay cloud-push (current),
(2) DNS-redirect the device to a local broker — only viable if the device does not pin
certificates (test plan, not execution), (3) hardware: ESP32/ESPHome on the unit's wired
controller bus (Modbus RS485 is common on Amitime units — **unverified for this model**;
needs photos of the controller board/connector).

## Acceptance criteria
- [ ] Decision record states outcome with cited evidence lines.
- [ ] `backlog/T15-*.md` updated to match the outcome (scope + points) and `progress.py` re-run.
