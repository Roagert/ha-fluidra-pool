# Drafted PR closing comments (T17)

Not posted. Post them, and close the PRs, once #11 (2.0.0) is merged.

Lead notes:
- PR #10's diff now shows 14 commits / 42 files: its base is the pre-T01 history (`bfb14c4`),
  so it carries the purged commits. Close it, don't merge or rebase it. Fork and cached
  `refs/pull/10` are already tracked in T01/U01.
- PR #7's branch was rewritten by T01 (`573f973`); closing it does not delete the branch.

## PR #7 — feat: add Fluidra local CLI discovery tooling

> Closing this in favour of the 2.0.0 rework (#11). This branch was the research scratchpad
> for local control; here is what happened to it.
>
> **Carried into 2.0.0**
> - The capture research (`docs/unifi-network-capture-notes.md`,
>   `docs/local-solution-next-steps.md`, and the lessons of the 2026-05-17 AP captures: a
>   laptop can't see the pump's unicast traffic, capture on the AP's `br0`, retry on `-i any`,
>   switch mirror as a fallback) is now the copy-paste runbook `docs/LOCAL_CAPTURE.md`.
> - Reading those captures by hand is now `scripts/analyze_capture.py` (stdlib only; pcap and
>   pcapng; per-peer table, DNS, TLS SNI, flags for LAN, broadcast and MQTT traffic; no payload
>   bytes unless `--payload`), with tests.
> - The transport conclusions (no `commandAndControl.localUdp` for `amt`, local UDP/BLE control
>   is an iQBridge RS path in the app, BLE SPP is provisioning only, LAN scans found no open
>   port on the pump) are in `PROTOCOL.md` §5–6. `PROTOCOL_FINDINGS.md` was merged into `PROTOCOL.md`.
>
> **Not carried over, and why**
> - `scripts/fluidra_cloud.py` (+ doc, tests, fixture): the integration now has its own
>   Cognito login (MFA, refresh token) and REST client, and Download diagnostics covers the
>   read commands. A second client in `scripts/` would be duplicate code that keeps tokens on disk.
> - `scripts/fluidra_local.py` (+ doc, tests): the LAN/TCP/MQTT probes found nothing on the
>   pump, and local research now goes only through the AP capture. The firewall-plan and
>   write-validation helpers have no user in the integration.
> - `docs/subagent-*.md` and `docs/local-heatpump-connection-plan.md`: working notes; their
>   conclusions are in `PROTOCOL.md`, and the LAN-discovery and MQTT reports probed the Home
>   Assistant host by mistake (corrected later on this branch).
> - `docs/flutter-app-proxy-capture.md`: the app's HTTPS goes to the same cloud API the
>   integration already uses, so a proxy doesn't answer the local question.
> - The 2026-05-17 capture write-ups: one-off results (only ARP from the pump on the AP). The
>   full AP capture with the runbook decides the local path, recorded in `docs/LOCAL_DECISION.md`.
>
> The branch stays available for reference.

## PR #10 — fix: start WebSocket listener as a background task (@kifeo)

> Thank you @kifeo, for the clear diagnosis of #9 and for a fix that was easy to verify.
> 2.0.0 rewrites the coordinator, so this PR can't be merged as-is, but your fix is in it:
> the WebSocket listener now starts as a config-entry background task, so Home Assistant
> startup no longer waits about 5 minutes, and unloading the entry cancels it. A regression
> test fails if it goes back to `hass.async_create_task`. The commit carries your
> `Co-authored-by`, and the changelog thanks you (Fixed, #9).
>
> Closing this now that 2.0.0 (#11) is merged. Thanks again!
