# Flutter app proxy capture workflow for Fluidra/iAquaLink+

Goal: inspect HTTP(S) traffic from the official Flutter app without confusing proxy limitations with protocol facts.

## Installed tools on Hermes host

Installed user-local, not system-wide:

```text
~/bin/charles  -> ~/opt/charles/bin/charles
~/bin/proxyman -> ~/opt/proxyman/proxyman
```

Versions/status:

```text
Charles Proxy 4.6.8
Proxyman Linux binary installed from https://proxyman.com/release/linux/proxyman_latest
```

This machine currently has no graphical desktop session (`DISPLAY` is empty), so Proxyman is installed but cannot be launched interactively here unless an X/Wayland desktop or remote display is provided. Charles works headless.

## Current Charles headless proxy

Charles was started headless and is listening on:

```text
proxy host: 192.168.1.62
proxy port: 8888
```

Smoke test from localhost through Charles succeeded.

Charles SSL certificate exported locally:

```text
/tmp/charles-ssl-proxying-certificate.pem
```

For phone installation, the easier Charles path is usually:

```text
http://chls.pro/ssl
```

while the phone is using the Charles proxy.

## Phone setup

1. Put phone on same Wi‑Fi.
2. Configure Wi‑Fi manual HTTP proxy:

```text
Server: 192.168.1.62
Port: 8888
```

3. Prove the phone reaches Charles:
   - Open Safari/Chrome on the phone.
   - Visit `http://example.com`.
   - The request should appear in Charles.
4. Install Charles certificate:
   - Visit `http://chls.pro/ssl` on the phone.
   - iOS: install profile, then enable full trust in Settings → General → About → Certificate Trust Settings.
   - Android: install as user CA if allowed.
5. Re-test with browser HTTPS:
   - Visit `https://example.com`.
   - If trusted correctly, Charles should show HTTPS metadata/content for browser traffic.

## Flutter/offical-app caveats

The StackOverflow/flutter-network-debugger style solution is mostly for apps where we control source code. It requires adding/debugging code in the Flutter app. It does not instrument a signed third-party production app.

Official Flutter apps may:

- ignore the OS proxy,
- use Dart networking that bypasses Wi‑Fi proxy settings,
- use certificate pinning,
- use non-HTTP local transports that Charles/Proxyman cannot see.

Therefore:

- Browser traffic captured: proves phone → proxy works.
- Fluidra app HTTPS captured: confirms app honors proxy and/or does not block this MITM path.
- No Fluidra traffic captured: does **not** prove no app traffic; it may bypass proxy or pin certs.
- Cloud-only HAR: confirms captured HTTP flow is cloud-based, but does **not** rule out UDP/BLE/local transport.

## Safe Fluidra capture action

Once browser traffic is visible in Charles:

1. Clear Charles session.
2. Open iAquaLink+/Fluidra app.
3. Refresh/open heat pump page.
4. Do one harmless reversible action, for example setpoint `22 → 23 → 22`.
5. Export session as HAR/Charles session.
6. Analyze only redacted metadata:
   - host counts,
   - methods/statuses,
   - paths,
   - references to `192.168.1.29`, `LG24440781`, `localUdp`, `udpKey`, `mqtt`, `commandAndControl`, `components/13`, `components/14`, `components/15`.

Never publish raw Authorization headers, cookies, bearer tokens, refresh tokens, API keys, or full private payloads.

## Useful Charles commands

Start Charles headless:

```bash
~/bin/charles --headless
```

Export Charles SSL cert:

```bash
~/bin/charles ssl export /tmp/charles-ssl-proxying-certificate.pem
```

Check listener:

```bash
ss -lntp | grep ':8888'
```

Test local proxy:

```bash
curl -x http://127.0.0.1:8888 -I http://example.com/
```

## Proxyman notes

Proxyman Linux was installed, but this host currently has no GUI session. In a desktop session it can be started with:

```bash
~/bin/proxyman --no-sandbox
```

Without `--no-sandbox`, the AppImage aborts because the embedded Chromium sandbox is not setuid-root. Without `DISPLAY`, it cannot initialize the UI.
