# T18 final review — findings and verdicts

Four independent read-only reviewers (python-reviewer, silent-failure-hunter,
security-reviewer, code-simplifier — `.claude/agents/`) over `custom_components/fluidra_pool/`
at `50855c8`. Lead verdicts below; **fix** = done in the T18 commit with a test where
behaviour changes.

| # | Finding | Found by | Verdict |
|---|---|---|---|
| F1 | Every push calls `async_set_updated_data`: resets the 5-min poll timer, cancels the post-command re-read, flips `last_update_success` → with frequent pushes `alarms` is never refreshed and an ignored command stays shown as applied | python, silent | **fix**: `async_update_listeners()` |
| F2 | Any exception inside the push callback (or malformed push: non-str `deviceId`, deep JSON, `ts` = inf/far future) kills the WS listener for good | silent, security | **fix**: validate in `_parse_push` (str deviceId, finite ts ≤ now+60 else now, catch RecursionError) + `try/except Exception: _LOGGER.exception` around `on_update` |
| F3 | `FluidraAuthError` in the WS loop is retried every ≤300 s with the rejected password → Cognito lockout risk, can make reauth fail | python, silent | **fix**: return on auth error (poll owns reauth; reload restarts the listener) |
| F4 | Entry title `Fluidra Pool (<e-mail>)` is logged by HA core on auth failure / setup retry | python, security | **fix**: title `Fluidra Pool`; v1→v2 migration retitles `Fluidra Pool (<username>)` (2.0.0 unreleased, so v2 can absorb it) |
| F5 | Offline pump (cloud keeps last values, accepts PUTs) shows as available with frozen values | silent | **fix**: also require `info.connectivity.connected` (default True if absent; verify in U03) |
| F6 | A push for a device already read during a poll is overwritten by that poll | python | **fix**: merge newer-ts values after the loop against current `self.data` |
| F7 | uiconfig fetched in the poll path: a timeout/401 there fails the poll (or starts reauth) although only diagnostics use it | python | **fix**: fetch uiconfig on demand in `diagnostics.py`; drop `coordinator.uiconfig` |
| F8 | `climate.set_temperature` with `hvac_mode` ignores the mode | python | **fix**: apply `hvac_mode` kwarg first |
| F9 | Cloud device ids inserted into URL paths unescaped (same-origin path traversal) | security | **fix**: `quote(device_id, safe="")` |
| F10 | No user-visible signal when WS push is down for good | silent | **fix**: one WARNING when backoff reaches 300 s, INFO on recovery |
| F11 | A device dropped from a poll (components read failed) only logs at debug | silent, python | **fix**: WARNING the first time a device drops (not every poll) |
| F12 | gitleaks (full history) flags Fluidra's public Firebase key in deleted RE dumps | security | **fix**: `.gitleaksignore` with the 2 fingerprints |
| F13 | Owner's LAN IP/MAC as analyzer defaults, in tests and synthetic pcap | security | **fix**: required `--hp-ip/--hp-mac`; tests/fixture use 192.0.2.x / 02:00:00:00:00:01; runbook passes them |
| F14 | `local_client.py` unused 210-line stub ships to users | python, silent | **fix**: delete (both T15 outcomes delete it) |
| F15 | Dead consts (`API_ENDPOINT_POOLS`, `COGNITO_POOL_ID`, `TOKEN_REFRESH_THRESHOLD`), `ClientId` built 3×, duplicate `TIMEOUT`, duplicate `available` in component sensor | simplifier | **fix** |
| — | First refresh: a failing device gets no entities until reload | python | **won't fix** (raising would let one broken device block setup forever); covered by F11's warning |
| — | Delete `strings.json` (dup of en.json) | simplifier | **won't fix**: hassfest/translation tooling risk for 87 JSON lines |
| — | Docstring trims, test-helper dedupe, `__init__`-only-key removals | simplifier | **won't fix**: cosmetic churn |
| — | LOC target ≤ 900 | T18 file | **re-scoped**: ~1,050 after fixes without cutting features; target was set before T12 added other-device support |
| — | `docs/LOCAL_CAPTURE.md` holds owner LAN IPs/MAC | security | **after U02**: replace with placeholders |
| — | `backlog/` mentions owner first name, device serial, AP/switch IPs | security | **noted** for Thomas: planning docs; serial already public in history |
