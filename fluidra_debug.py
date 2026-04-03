#!/usr/bin/env python3
"""
Fluidra Pool — Diagnostic & Protocol Capture Script
====================================================
Run this to capture everything needed for local protocol reverse engineering:
  - Full raw API responses (devices, components, uiconfig)
  - commandAndControl.localUdp endpoint (if device is on LAN)
  - Live WebSocket message format (10 seconds capture)
  - Component ID → value map
  - Pool & user data

Usage:
  python3 fluidra_debug.py <email> <password>
  python3 fluidra_debug.py <email> <password> --ws      # Also capture 30s of WS traffic
  python3 fluidra_debug.py <email> <password> --ws --zigbee  # Show Zigbee AT cmd info too

Output:
  fluidra_debug_<timestamp>.json  — machine-readable full dump
  fluidra_debug_<timestamp>.txt   — human-readable summary
"""
import argparse
import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Any, Dict, Optional

# ── Dependencies ──────────────────────────────────────────────────────────────
try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("Missing: pip install boto3")
    sys.exit(1)

try:
    import aiohttp
except ImportError:
    print("Missing: pip install aiohttp")
    sys.exit(1)

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# ── Constants ─────────────────────────────────────────────────────────────────
COGNITO_REGION    = "eu-west-1"
COGNITO_CLIENT_ID = "g3njunelkcbtefosqm9bdhhq1"
API_BASE          = "https://api.fluidra-emea.com"
WS_URL            = "wss://ws.fluidra-emea.com"

COMPONENT_NAMES = {
    13: "Power (0=off, 1=on)",
    14: "Mode (0=SmartHeat,1=SmartCool,2=SmartAuto,3=BoostHeat,4=SilenceHeat,5=BoostCool,6=SilenceCool)",
    15: "Set Temperature (×0.1 °C)",
    19: "Water Temperature (×0.1 °C)",
}

# ── Auth ──────────────────────────────────────────────────────────────────────

def cognito_login(username: str, password: str) -> Optional[Dict]:
    """Authenticate via AWS Cognito USER_PASSWORD_AUTH flow."""
    client = boto3.client("cognito-idp", region_name=COGNITO_REGION)
    try:
        resp = client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
        ar = resp["AuthenticationResult"]
        return {
            "access_token": ar["AccessToken"],
            "id_token":     ar["IdToken"],
            "refresh_token": ar["RefreshToken"],
            "expires_in":   ar["ExpiresIn"],
        }
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "?")
        msg  = e.response.get("Error", {}).get("Message", str(e))
        print(f"\n[AUTH FAILED] {code}: {msg}")
        return None

# ── API helpers ───────────────────────────────────────────────────────────────

def _headers(token: str) -> Dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

async def get(session: aiohttp.ClientSession, token: str, url: str) -> Dict:
    """GET and return JSON dict (or error dict)."""
    try:
        async with session.get(url, headers=_headers(token), timeout=aiohttp.ClientTimeout(total=15)) as r:
            text = await r.text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {"_raw": text}
            return {"_status": r.status, "_url": url, "data": data}
    except Exception as e:
        return {"_status": -1, "_url": url, "_error": str(e)}

# ── Component decoder ─────────────────────────────────────────────────────────

def decode_components(raw_components: Any) -> Dict:
    """Turn the raw components API response into a clean id→value map."""
    result = {}
    items = []
    if isinstance(raw_components, list):
        items = raw_components
    elif isinstance(raw_components, dict):
        # Sometimes wrapped in { records: [...] } or { components: [...] }
        for key in ("records", "components", "data", "items"):
            if key in raw_components:
                items = raw_components[key]
                break
        if not items:
            items = [raw_components]

    for item in items:
        if not isinstance(item, dict):
            continue
        comp_id = item.get("componentId") or item.get("id") or item.get("componentID")
        if comp_id is None:
            continue
        comp_id = int(comp_id)
        reported = item.get("reportedValue") if "reportedValue" in item else item.get("value")
        desired  = item.get("desiredValue")
        name     = COMPONENT_NAMES.get(comp_id, "")

        result[comp_id] = {
            "reported": reported,
            "desired":  desired,
            "name":     name,
            "_raw":     item,
        }
        if comp_id in (15, 19) and reported is not None:
            try:
                result[comp_id]["celsius"] = round(int(reported) / 10.0, 1)
            except (TypeError, ValueError):
                pass

    return result

# ── WebSocket capture ─────────────────────────────────────────────────────────

async def capture_websocket(token: str, device_ids: list, duration: int = 30) -> list:
    """Connect to Fluidra WebSocket, subscribe to all devices, capture messages."""
    if not HAS_WEBSOCKETS:
        return [{"error": "websockets package not installed: pip install websockets"}]

    messages = []
    print(f"\n[WS] Connecting to {WS_URL} for {duration}s...")
    try:
        async with websockets.connect(
            WS_URL,
            extra_headers={"Authorization": f"Bearer {token}"},
            ping_interval=20,
            open_timeout=10,
        ) as ws:
            print("[WS] Connected!")
            for dev_id in device_ids:
                sub = json.dumps({
                    "action": "subsDevice",
                    "deviceType": "connected",
                    "deviceId": dev_id,
                })
                await ws.send(sub)
                print(f"[WS] Subscribed to device {dev_id}")

            deadline = asyncio.get_event_loop().time() + duration
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 5))
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = {"_raw_text": raw}
                    messages.append(parsed)
                    print(f"[WS] Message: {json.dumps(parsed)[:120]}")
                except asyncio.TimeoutError:
                    print(f"[WS] {int(remaining)}s remaining, no message…", end="\r")
                except websockets.exceptions.ConnectionClosed:
                    print("[WS] Connection closed by server")
                    break
    except Exception as e:
        messages.append({"error": str(e)})
        print(f"[WS] Error: {e}")

    return messages

# ── Local UDP detector ────────────────────────────────────────────────────────

def extract_local_udp(device_data: Any) -> Optional[Dict]:
    """Recursively search a device object for commandAndControl.localUdp."""
    if not isinstance(device_data, dict):
        return None

    # Direct hit
    cnc = device_data.get("commandAndControl") or device_data.get("command_and_control")
    if isinstance(cnc, dict):
        local_udp = cnc.get("localUdp") or cnc.get("local_udp")
        if local_udp:
            return local_udp
        # Also check for cloud/ble keys as siblings
        return {"commandAndControl_keys": list(cnc.keys()), "full": cnc}

    # Search nested
    for v in device_data.values():
        if isinstance(v, dict):
            found = extract_local_udp(v)
            if found:
                return found
        elif isinstance(v, list):
            for item in v:
                found = extract_local_udp(item)
                if found:
                    return found
    return None

# ── Main ──────────────────────────────────────────────────────────────────────

async def main(username: str, password: str, capture_ws: bool, show_zigbee: bool):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = f"fluidra_debug_{ts}.json"
    out_txt  = f"fluidra_debug_{ts}.txt"

    dump = {
        "meta": {"timestamp": ts, "username": username},
        "auth": {},
        "endpoints": {},
        "devices": {},
        "components": {},
        "local_udp": {},
        "websocket_messages": [],
        "zigbee_info": {},
        "analysis": {},
    }
    lines = []

    def log(msg=""):
        print(msg)
        lines.append(msg)

    log("=" * 70)
    log("  Fluidra Pool Diagnostic Script")
    log(f"  Run at: {ts}")
    log("=" * 70)

    # ── Auth
    log("\n[1/6] Authenticating...")
    tokens = await asyncio.get_event_loop().run_in_executor(None, cognito_login, username, password)
    if not tokens:
        log("Authentication failed. Check email/password.")
        return
    token = tokens["access_token"]
    dump["auth"] = {"ok": True, "expires_in": tokens["expires_in"]}
    log(f"  OK — token expires in {tokens['expires_in']}s")
    log(f"  Access token: {token[:16]}...{token[-8:]}")

    async with aiohttp.ClientSession() as session:

        # ── Fetch all endpoints
        log("\n[2/6] Fetching API data...")
        endpoints = {
            "user_me":         f"{API_BASE}/generic/users/me",
            "user_pools":      f"{API_BASE}/generic/users/me/pools",
            "devices_list":    f"{API_BASE}/generic/devices",
            # Legacy endpoint (to compare)
            "consumer_legacy": f"{API_BASE}/mobile/consumers/me",
        }
        for name, url in endpoints.items():
            log(f"  GET {url}")
            resp = await get(session, token, url)
            dump["endpoints"][name] = resp
            status = resp["_status"]
            log(f"       → HTTP {status}")

        # ── Pool-level status
        pools_resp = dump["endpoints"]["user_pools"]
        pool_ids = []
        try:
            pools_data = pools_resp.get("data", {})
            if isinstance(pools_data, list):
                pool_ids = [p.get("id") or p.get("poolId") for p in pools_data if isinstance(p, dict)]
            elif isinstance(pools_data, dict):
                records = pools_data.get("records") or pools_data.get("pools") or []
                pool_ids = [p.get("id") or p.get("poolId") for p in records if isinstance(p, dict)]
        except Exception:
            pass
        pool_ids = [p for p in pool_ids if p]
        log(f"  Found {len(pool_ids)} pool(s): {pool_ids}")

        for pool_id in pool_ids:
            url = f"{API_BASE}/generic/pools/{pool_id}/status"
            log(f"  GET {url}")
            resp = await get(session, token, url)
            dump["endpoints"][f"pool_status_{pool_id}"] = resp
            log(f"       → HTTP {resp['_status']}")

        # ── Devices
        log("\n[3/6] Fetching device details...")
        devices_raw = dump["endpoints"]["devices_list"].get("data", {})
        device_ids = []

        if isinstance(devices_raw, list):
            device_list = devices_raw
        elif isinstance(devices_raw, dict):
            device_list = (devices_raw.get("records") or
                           devices_raw.get("devices") or
                           devices_raw.get("data") or [])
        else:
            device_list = []

        for dev in device_list:
            if not isinstance(dev, dict):
                continue
            dev_id = dev.get("id") or dev.get("deviceId") or dev.get("serialNumber")
            if not dev_id:
                continue
            device_ids.append(str(dev_id))
            dump["devices"][str(dev_id)] = dev

            # Full device detail (includes commandAndControl)
            for suffix in ["", "?deviceType=connected"]:
                url = f"{API_BASE}/generic/devices/{dev_id}{suffix}"
                log(f"  GET {url}")
                resp = await get(session, token, url)
                key = f"device_{dev_id}" + ("_connected" if suffix else "_raw")
                dump["endpoints"][key] = resp
                log(f"       → HTTP {resp['_status']}")

                # Check for localUdp immediately
                local_udp = extract_local_udp(resp.get("data", {}))
                if local_udp:
                    dump["local_udp"][str(dev_id)] = local_udp
                    log(f"  *** LOCAL UDP FOUND for device {dev_id}: {json.dumps(local_udp)}")

        log(f"\n  Device IDs: {device_ids}")

        # ── Components
        log("\n[4/6] Fetching component data...")
        for dev_id in device_ids:
            for suffix in ["", "?deviceType=connected"]:
                url = f"{API_BASE}/generic/devices/{dev_id}/components{suffix}"
                log(f"  GET {url}")
                resp = await get(session, token, url)
                key = f"components_{dev_id}" + ("_connected" if suffix else "_raw")
                dump["endpoints"][key] = resp
                status = resp["_status"]
                log(f"       → HTTP {status}")

                if status == 200:
                    parsed = decode_components(resp.get("data", {}))
                    dump["components"][key] = parsed
                    log(f"       → {len(parsed)} components")
                    for cid, cdata in sorted(parsed.items()):
                        name  = cdata.get("name", "")
                        val   = cdata.get("reported")
                        extra = f"  [{cdata['celsius']}°C]" if "celsius" in cdata else ""
                        log(f"         ID {cid:>4}: reported={val!s:<8} desired={cdata.get('desired')!s:<8}  {name}{extra}")

            # UIConfig
            url = f"{API_BASE}/generic/devices/{dev_id}/uiconfig?appId=iaq&deviceType=connected"
            log(f"  GET {url}")
            resp = await get(session, token, url)
            dump["endpoints"][f"uiconfig_{dev_id}"] = resp
            log(f"       → HTTP {resp['_status']}")

        # ── WebSocket
        if capture_ws and device_ids:
            log(f"\n[5/6] Capturing WebSocket traffic (30 s)...")
            ws_msgs = await capture_websocket(token, device_ids, duration=30)
            dump["websocket_messages"] = ws_msgs
            log(f"  Captured {len(ws_msgs)} message(s)")
        else:
            log("\n[5/6] WebSocket capture skipped (use --ws to enable)")

        # ── Zigbee info
        if show_zigbee:
            log("\n[6/6] Looking for Zigbee / AT command info...")
            for dev_id in device_ids:
                for path in [
                    f"/generic/devices/{dev_id}/zigbee",
                    f"/generic/devices/{dev_id}/bridge",
                    f"/generic/devices/{dev_id}/bridged",
                    f"/generic/devices/{dev_id}/components?deviceType=connected&type=zigbee",
                ]:
                    url = f"{API_BASE}{path}"
                    resp = await get(session, token, url)
                    if resp["_status"] == 200:
                        log(f"  *** ZIGBEE endpoint found: {url}")
                        dump["zigbee_info"][url] = resp
                    else:
                        log(f"  {path} → {resp['_status']}")
        else:
            log("\n[6/6] Zigbee check skipped (use --zigbee to enable)")

    # ── Analysis
    log("\n" + "=" * 70)
    log("  ANALYSIS SUMMARY")
    log("=" * 70)

    # Local UDP
    if dump["local_udp"]:
        log("\n*** LOCAL UDP CONTROL AVAILABLE ***")
        for dev_id, info in dump["local_udp"].items():
            log(f"  Device {dev_id}:")
            log(f"  {json.dumps(info, indent=4)}")
        dump["analysis"]["local_control"] = "AVAILABLE"
    else:
        log("\n[ ] Local UDP: not found in API responses")
        log("    → Either device is not on LAN, or field name differs")
        log("    → Check 'commandAndControl' key in raw device JSON below")
        dump["analysis"]["local_control"] = "NOT_FOUND"

    # Key component values
    log("\n  Key Component Values (first device):")
    first_key = next((k for k in dump["components"] if "_connected" in k), None)
    if first_key:
        comps = dump["components"][first_key]
        for cid in [13, 14, 15, 19]:
            c = comps.get(cid)
            if c:
                val = c.get("reported")
                extra = f"  → {c['celsius']}°C" if "celsius" in c else ""
                log(f"    Component {cid}: {val}{extra}  ({c.get('name','')})")
            else:
                log(f"    Component {cid}: NOT FOUND in this response")

    # commandAndControl keys seen
    log("\n  'commandAndControl' keys found across all device responses:")
    cnc_found = False
    for key, resp in dump["endpoints"].items():
        if "device_" not in key:
            continue
        data = resp.get("data", {})
        if isinstance(data, dict):
            cnc = data.get("commandAndControl") or data.get("command_and_control")
            if cnc:
                log(f"    [{key}] keys: {list(cnc.keys()) if isinstance(cnc, dict) else type(cnc).__name__}")
                log(f"    Full: {json.dumps(cnc, indent=6)}")
                cnc_found = True
    if not cnc_found:
        log("    → None found. Full device JSON printed in output file.")

    # What the WebSocket messages looked like
    if dump["websocket_messages"]:
        log(f"\n  WebSocket messages ({len(dump['websocket_messages'])} total):")
        for i, m in enumerate(dump["websocket_messages"][:5]):
            log(f"    [{i}] {json.dumps(m)[:150]}")

    # Zigbee dongle advice
    log("\n  Zigbee Dongle Advice:")
    iqbridge_zb = any(
        "zb" in str(d.get("deviceType", "")).lower() or
        "zigbee" in str(d).lower()
        for d in dump["devices"].values()
    )
    if iqbridge_zb:
        log("  [iQBridge ZB detected]")
        log("  → A Zigbee dongle on Home Assistant would let you talk DIRECTLY to pool")
        log("    equipment bypassing iQBridge entirely.")
        log("  → Recommended: Sonoff Zigbee 3.0 USB Plus (CC2652P)")
        log("    or HUSBZB-1, or Conbee II")
        log("  → Use ZHA or Zigbee2MQTT integration in HA")
        log("  → Pairing code: use getZigbeeInstallCode AT command via Fluidra app")
        dump["analysis"]["zigbee_dongle"] = "RECOMMENDED — iQBridge ZB detected"
    else:
        log("  [iQBridge RS or unknown model]")
        log("  → iQBridge RS uses BLE, not Zigbee. A Zigbee dongle won't help here.")
        log("  → For RS: local UDP or BLE are the paths to local control")
        log("  → To check: look for 'ZB' or 'zigbee' in your device model string")
        dump["analysis"]["zigbee_dongle"] = "NOT_NEEDED — iQBridge RS (BLE)"

    log("\n" + "=" * 70)
    log(f"  Saved: {out_json}")
    log(f"  Saved: {out_txt}")
    log("=" * 70)

    # Write outputs
    with open(out_json, "w") as f:
        json.dump(dump, f, indent=2, default=str)

    with open(out_txt, "w") as f:
        f.write("\n".join(lines))

    # Print one final raw device dump to txt so the user can see commandAndControl
    with open(out_txt, "a") as f:
        f.write("\n\n" + "=" * 70 + "\n")
        f.write("RAW DEVICE RESPONSES (full)\n")
        f.write("=" * 70 + "\n")
        for key in dump["endpoints"]:
            if "device_" in key or "components_" in key:
                f.write(f"\n--- {key} ---\n")
                f.write(json.dumps(dump["endpoints"][key], indent=2, default=str))
                f.write("\n")

    print(f"\nDone. Share '{out_json}' for analysis.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fluidra Pool diagnostic tool")
    parser.add_argument("username", help="Fluidra account email")
    parser.add_argument("password", help="Fluidra account password")
    parser.add_argument("--ws",      action="store_true", help="Capture 30s of WebSocket traffic")
    parser.add_argument("--zigbee",  action="store_true", help="Probe Zigbee/AT-command endpoints")
    args = parser.parse_args()

    asyncio.run(main(args.username, args.password, args.ws, args.zigbee))
