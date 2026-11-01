# Progress: 61%  [############........]  (46/75 points)

in_progress counts half. Regenerate with `python3 backlog/progress.py`.

| ID | Task | Phase | Pts | Status | Owner |
|---|---|---|---|---|---|
| T01 | Purge secrets and PII from git history | 0-safety | 3 | done | agent |
| T02 | Repo hygiene — delete stale duplicates, dumps, junk | 1-foundation | 3 | done | agent |
| T03 | Add Karpathy guidelines + ECC review agents | 1-foundation | 1 | done | agent |
| T04 | Test harness + CI (pytest, hassfest, HACS) | 1-foundation | 3 | done | agent |
| T05 | aiohttp Cognito auth with MFA + refresh token (drop boto3) | 2-client | 5 | done | agent |
| T06 | FluidraApi — REST + WebSocket client (the local-ready seam) | 2-client | 3 | done | agent |
| T07 | Rewrite coordinator (1,140 → ~200 lines), fix startup block #9 | 3-core | 8 | done | agent |
| T08 | Config flow — MFA, reauth, compatible unique_id, translations | 3-core | 5 | done | agent |
| T09 | Redacted diagnostics download; remove dump_api_data service | 3-core | 2 | done | agent |
| T10 | Climate entity correctness (modes, presets, hvac_action, errors) | 4-entities | 5 | done | agent |
| T11 | Sensors, power switch, no-flow binary sensor; drop raw-JSON sensors | 4-entities | 5 | done | agent |
| T12 | Other devices — no crash, no bogus values, generic sensors | 4-entities | 5 | todo | agent |
| T13 | AP packet-capture runbook + pcap analyzer | 5-local | 3 | done | agent |
| T14 | Analyze capture → local-path decision record | 5-local | 3 | todo | agent |
| T15 | Local transport client (conditional on T14 outcome A) | 5-local | 8 | blocked | agent |
| T16 | Manifest, README, PROTOCOL, PRD v3, CHANGELOG | 6-release | 3 | todo | agent |
| T17 | Deprecate ha-fluidra-local + addon; resolve PR #7 / #10 | 6-release | 2 | todo | agent |
| T18 | Final review gate (security, silent failures, simplicity) | 6-release | 3 | todo | agent |
| U01 | Change Fluidra password (+ optional GitHub cache purge) | 0-safety | 1 | todo | user |
| U02 | Run the 3-minute AP capture | 5-local | 2 | todo | user |
| U03 | Live test on Thomas's Home Assistant + release | 6-release | 2 | todo | user |
