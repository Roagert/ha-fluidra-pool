#!/usr/bin/env python3
"""Fluidra EMEA cloud CLI for Amitime/Fluidra heat pumps.

The CLI is intentionally small and dependency-free so it can be used from a
Home Assistant host, a debug shell, or automation. It supports read operations
and confirmed-safe writes for Thomas's Fluidra/Swim&Fun/Amitime AMT heat pump
profile.

Credentials are read from --username/--password or FLUIDRA_USERNAME /
FLUIDRA_PASSWORD. You can also pass --access-token to skip Cognito login when
working from an already captured token.

Write commands are dry-run by default. Pass --yes to actually send the PUT.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

API_BASE_URL = "https://api.fluidra-emea.com"
COGNITO_ENDPOINT = "https://cognito-idp.eu-west-1.amazonaws.com/"
COGNITO_CLIENT_ID = "g3njunelkcbtefosqm9bdhhq1"
DEFAULT_DEVICE_ID = "LG24440781"
DEFAULT_USER_AGENT = (
    "com.fluidra.iaqualinkplus/1741857021 "
    "(Linux; U; Android 14; fr_FR; FluidraCloudCLI)"
)

POWER_COMPONENT = 13
MODE_COMPONENT = 14
SETPOINT_COMPONENT = 15
RUNNING_COMPONENT = 11
STATUS_COMPONENT = 17
WATER_TEMP_COMPONENT = 19
NO_FLOW_COMPONENT = 28
AIR_TEMP_COMPONENT = 67
EFFECTIVE_MODE_COMPONENT = 80
MIN_SETPOINT_COMPONENT = 81
MAX_SETPOINT_COMPONENT = 82
RUNNING_HOURS_COMPONENT = 0
RSSI_COMPONENT = 1
LOCAL_IP_COMPONENT = 2
SERIAL_COMPONENT = 3
FIRMWARE_COMPONENT = 4
THING_TYPE_COMPONENT = 5
MODEL_CODE_COMPONENT = 6
SIGNATURE_COMPONENT = 7
SUPPLY_VOLTAGE_COMPONENT = 74
WATER_INLET_COMPONENT = 68
WATER_OUTLET_COMPONENT = 69
INTERNAL_TEMP_COMPONENTS = (65, 66, 70)

MODE_NAMES = {
    0: "smart-heating",
    1: "smart-cooling",
    2: "smart-heating-cooling",
    3: "boost-heating",
    4: "silence-heating",
    5: "boost-cooling",
    6: "silence-cooling",
}
MODE_ALIASES = {
    "smart-heat": 0,
    "heat": 0,
    "smart-heating": 0,
    "smart-cool": 1,
    "cool": 1,
    "smart-cooling": 1,
    "auto": 2,
    "smart-auto": 2,
    "smart-heating-cooling": 2,
    "smart-heat-cool": 2,
    "heat-cool": 2,
    "boost-heat": 3,
    "boost-heating": 3,
    "silence-heat": 4,
    "silent-heat": 4,
    "eco-heat": 4,
    "silence-heating": 4,
    "boost-cool": 5,
    "boost-cooling": 5,
    "silence-cool": 6,
    "silent-cool": 6,
    "eco-cool": 6,
    "silence-cooling": 6,
}
SAFE_WRITE_RANGES = {
    POWER_COMPONENT: (0, 1),
    MODE_COMPONENT: (0, 6),
    SETPOINT_COMPONENT: (70, 400),  # confirmed uiconfig bounds: 7.0-40.0 C, raw x10
}


class FluidraCloudError(RuntimeError):
    """Raised for Fluidra cloud request/auth failures."""


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    id_token: str | None = None
    refresh_token: str | None = None
    expires_at: int | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "id_token": self.id_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "AuthTokens":
        token = data.get("access_token") or data.get("AccessToken")
        if not isinstance(token, str) or not token:
            raise ValueError("token cache does not contain access_token")
        return cls(
            access_token=token,
            id_token=data.get("id_token") or data.get("IdToken"),
            refresh_token=data.get("refresh_token") or data.get("RefreshToken"),
            expires_at=data.get("expires_at"),
        )


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def normalize_components(raw: Any) -> dict[int, dict[str, Any]]:
    """Normalize Fluidra component list/dict shapes into id -> component payload."""

    if isinstance(raw, Mapping):
        for key in ("components", "records", "items", "data"):
            value = raw.get(key)
            if isinstance(value, (list, dict)):
                return normalize_components(value)
        result: dict[int, dict[str, Any]] = {}
        for key, value in raw.items():
            if str(key).isdigit():
                if isinstance(value, Mapping):
                    result[int(key)] = dict(value)
                else:
                    result[int(key)] = {"id": int(key), "reportedValue": value}
        return result

    result = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            cid = item.get("id") or item.get("componentId") or item.get("componentID")
            if cid is None or not str(cid).isdigit():
                continue
            result[int(cid)] = dict(item)
    return result


def component_value(components: Mapping[int, Mapping[str, Any]], component_id: int) -> Any:
    component = components.get(component_id)
    if component is None:
        return None
    if "reportedValue" in component:
        return component.get("reportedValue")
    if "reported" in component:
        return component.get("reported")
    return component.get("value")


def raw_to_celsius(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value) / 10.0, 1)
    except (TypeError, ValueError):
        return None


def signed16(value: Any) -> int | None:
    try:
        raw = int(value)
    except (TypeError, ValueError):
        return None
    return raw - 65536 if raw > 32767 else raw


def decode_heatpump_status(raw_components: Any) -> dict[str, Any]:
    components = normalize_components(raw_components)
    power_raw = component_value(components, POWER_COMPONENT)
    mode_raw = component_value(components, MODE_COMPONENT)
    effective_mode_raw = component_value(components, EFFECTIVE_MODE_COMPONENT)
    status_raw = component_value(components, STATUS_COMPONENT)
    no_flow_raw = component_value(components, NO_FLOW_COMPONENT)

    status = {
        "device_id": component_value(components, SERIAL_COMPONENT),
        "thing_type": component_value(components, THING_TYPE_COMPONENT),
        "signature": component_value(components, SIGNATURE_COMPONENT),
        "firmware": component_value(components, FIRMWARE_COMPONENT),
        "local_ip": component_value(components, LOCAL_IP_COMPONENT),
        "wifi_rssi_dbm": component_value(components, RSSI_COMPONENT),
        "running_hours": component_value(components, RUNNING_HOURS_COMPONENT),
        "power": "on" if power_raw == 1 else "off" if power_raw == 0 else "unknown",
        "power_raw": power_raw,
        "running": bool(component_value(components, RUNNING_COMPONENT))
        if component_value(components, RUNNING_COMPONENT) is not None
        else None,
        "mode": MODE_NAMES.get(mode_raw, "unknown"),
        "mode_raw": mode_raw,
        "effective_mode": MODE_NAMES.get(effective_mode_raw, "unknown"),
        "effective_mode_raw": effective_mode_raw,
        "set_temperature_c": raw_to_celsius(component_value(components, SETPOINT_COMPONENT)),
        "water_temperature_c": raw_to_celsius(component_value(components, WATER_TEMP_COMPONENT)),
        "air_temperature_c": raw_to_celsius(component_value(components, AIR_TEMP_COMPONENT)),
        "water_inlet_temperature_c": raw_to_celsius(component_value(components, WATER_INLET_COMPONENT)),
        "water_outlet_temperature_c": raw_to_celsius(component_value(components, WATER_OUTLET_COMPONENT)),
        "internal_temperatures_c": {
            str(cid): raw_to_celsius(component_value(components, cid))
            for cid in INTERNAL_TEMP_COMPONENTS
            if raw_to_celsius(component_value(components, cid)) is not None
        },
        "no_flow": True if no_flow_raw == 1 else False if no_flow_raw == 0 else None,
        "no_flow_raw": no_flow_raw,
        "status": "ok" if status_raw == 0 else "error-or-hidden" if status_raw == 7 else "unknown",
        "status_raw": status_raw,
        "min_setpoint_c": component_value(components, MIN_SETPOINT_COMPONENT),
        "max_setpoint_c": component_value(components, MAX_SETPOINT_COMPONENT),
        "supply_voltage_v": component_value(components, SUPPLY_VOLTAGE_COMPONENT),
        "signed_diagnostics": {
            "72_signed16": signed16(component_value(components, 72)),
        },
        "raw_component_count": len(components),
    }
    return status


def validate_write(component_id: int, raw_value: int) -> list[str]:
    if component_id not in SAFE_WRITE_RANGES:
        return [f"component {component_id} is not in the confirmed safe write set {sorted(SAFE_WRITE_RANGES)}"]
    minimum, maximum = SAFE_WRITE_RANGES[component_id]
    if not minimum <= raw_value <= maximum:
        return [f"component {component_id} value {raw_value} is outside {minimum}..{maximum}"]
    return []


def raw_setpoint_from_celsius(value: float) -> int:
    return int(round(value * 10))


def raw_mode(value: str | int) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip().lower().replace("_", "-")
    if text.isdigit():
        return int(text)
    if text not in MODE_ALIASES:
        raise ValueError(f"unknown mode {value!r}; use one of {sorted(set(MODE_ALIASES))} or 0..6")
    return MODE_ALIASES[text]


def load_json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


class FluidraCloudClient:
    def __init__(self, access_token: str, *, timeout: float = 20.0, user_agent: str = DEFAULT_USER_AGENT) -> None:
        self.access_token = access_token
        self.timeout = timeout
        self.user_agent = user_agent

    @classmethod
    def login(cls, username: str, password: str, *, timeout: float = 20.0) -> tuple["FluidraCloudClient", AuthTokens]:
        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": COGNITO_CLIENT_ID,
            "AuthParameters": {"USERNAME": username, "PASSWORD": password},
        }
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        data = _http_json("POST", COGNITO_ENDPOINT, headers=headers, payload=payload, timeout=timeout)
        try:
            auth = data["AuthenticationResult"]
            tokens = AuthTokens(
                access_token=auth["AccessToken"],
                id_token=auth.get("IdToken"),
                refresh_token=auth.get("RefreshToken"),
                expires_at=int(time.time()) + int(auth.get("ExpiresIn", 3600)),
            )
        except (KeyError, TypeError) as err:
            raise FluidraCloudError(f"unexpected Cognito response shape: {data!r}") from err
        return cls(tokens.access_token, timeout=timeout), tokens

    def request(self, method: str, path_or_url: str, payload: Any = None) -> Any:
        url = path_or_url if path_or_url.startswith("http") else f"{API_BASE_URL}{path_or_url}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": self.user_agent,
        }
        return _http_json(method, url, headers=headers, payload=payload, timeout=self.timeout)

    def devices(self) -> Any:
        return self.request("GET", "/generic/devices?deviceType=connected")

    def components(self, device_id: str) -> Any:
        quoted = urllib.parse.quote(device_id, safe="")
        return self.request("GET", f"/generic/devices/{quoted}/components?deviceType=connected")

    def uiconfig(self, device_id: str) -> Any:
        quoted = urllib.parse.quote(device_id, safe="")
        return self.request("GET", f"/generic/devices/{quoted}/uiconfig?appId=iaq&deviceType=connected")

    def set_component(self, device_id: str, component_id: int, raw_value: int) -> Any:
        quoted = urllib.parse.quote(device_id, safe="")
        return self.request(
            "PUT",
            f"/generic/devices/{quoted}/components/{component_id}?deviceType=connected",
            {"desiredValue": raw_value},
        )


def _http_json(method: str, url: str, *, headers: Mapping[str, str], payload: Any = None, timeout: float = 20.0) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method=method.upper(), headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise FluidraCloudError(f"HTTP {err.code} {err.reason} for {method.upper()} {url}: {detail}") from err
    except urllib.error.URLError as err:
        raise FluidraCloudError(f"request failed for {method.upper()} {url}: {err}") from err
    except json.JSONDecodeError as err:
        raise FluidraCloudError(f"non-JSON response from {method.upper()} {url}: {err}") from err


def token_cache_path(path: str | None) -> Path:
    if path:
        return Path(path).expanduser()
    return Path(os.environ.get("FLUIDRA_TOKEN_CACHE", "~/.cache/fluidra-cloud/token.json")).expanduser()


def get_client(args: argparse.Namespace) -> FluidraCloudClient:
    if args.access_token:
        return FluidraCloudClient(args.access_token, timeout=args.timeout)

    cache = token_cache_path(args.token_cache)
    if not args.no_cache and cache.exists():
        try:
            tokens = AuthTokens.from_json(json.loads(cache.read_text()))
            if not tokens.expires_at or tokens.expires_at > int(time.time()) + 60:
                return FluidraCloudClient(tokens.access_token, timeout=args.timeout)
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    username = args.username or os.environ.get("FLUIDRA_USERNAME")
    password = args.password or os.environ.get("FLUIDRA_PASSWORD")
    if not username or not password:
        raise FluidraCloudError("provide --username/--password, FLUIDRA_USERNAME/FLUIDRA_PASSWORD, or --access-token")

    client, tokens = FluidraCloudClient.login(username, password, timeout=args.timeout)
    if not args.no_cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(tokens.to_json(), indent=2))
        cache.chmod(0o600)
    return client


def command_devices(args: argparse.Namespace) -> int:
    print_json(get_client(args).devices())
    return 0


def command_components(args: argparse.Namespace) -> int:
    data = get_client(args).components(args.device_id)
    print_json(data)
    return 0


def command_uiconfig(args: argparse.Namespace) -> int:
    data = get_client(args).uiconfig(args.device_id)
    print_json(data)
    return 0


def command_status(args: argparse.Namespace) -> int:
    data = load_json_file(args.components_json) if args.components_json else get_client(args).components(args.device_id)
    print_json(decode_heatpump_status(data))
    return 0


def command_write(args: argparse.Namespace) -> int:
    errors = validate_write(args.component_id, args.raw_value)
    if errors:
        print_json({"ok": False, "errors": errors})
        return 2
    request = {
        "device_id": args.device_id,
        "component_id": args.component_id,
        "desiredValue": args.raw_value,
    }
    if not args.yes:
        print_json({"ok": True, "dry_run": True, "request": request, "note": "pass --yes to send the cloud write"})
        return 0
    response = get_client(args).set_component(args.device_id, args.component_id, args.raw_value)
    print_json({"ok": True, "dry_run": False, "request": request, "response": response})
    return 0


def command_set_power(args: argparse.Namespace) -> int:
    args.component_id = POWER_COMPONENT
    args.raw_value = 1 if args.state == "on" else 0
    return command_write(args)


def command_set_mode(args: argparse.Namespace) -> int:
    try:
        args.raw_value = raw_mode(args.mode)
    except ValueError as err:
        print_json({"ok": False, "errors": [str(err)]})
        return 2
    args.component_id = MODE_COMPONENT
    return command_write(args)


def command_set_setpoint(args: argparse.Namespace) -> int:
    args.component_id = SETPOINT_COMPONENT
    args.raw_value = raw_setpoint_from_celsius(args.temperature_c)
    return command_write(args)


def command_decode_file(args: argparse.Namespace) -> int:
    print_json(decode_heatpump_status(load_json_file(args.components_json)))
    return 0


def add_auth_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--username", help="Fluidra/iAquaLink+ account email; or FLUIDRA_USERNAME")
    parser.add_argument("--password", help="Fluidra/iAquaLink+ password; or FLUIDRA_PASSWORD")
    parser.add_argument("--access-token", help="Existing Cognito access token; skips login")
    parser.add_argument("--token-cache", help="Token cache path; default ~/.cache/fluidra-cloud/token.json")
    parser.add_argument("--no-cache", action="store_true", help="Do not read/write the token cache")
    parser.add_argument("--timeout", type=float, default=20.0)


def add_write_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID)
    parser.add_argument("--yes", action="store_true", help="Actually send the write; default is dry-run")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fluidra EMEA cloud CLI for AMT/Amitime heat pumps")
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID, help=f"Default device id (default: {DEFAULT_DEVICE_ID})")
    add_auth_args(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    devices = sub.add_parser("devices", help="List cloud devices")
    devices.set_defaults(func=command_devices)

    components = sub.add_parser("components", help="Fetch raw component list for a device")
    components.set_defaults(func=command_components)

    ui = sub.add_parser("uiconfig", help="Fetch iAquaLink+ UI config for a device")
    ui.set_defaults(func=command_uiconfig)

    status = sub.add_parser("status", help="Fetch and decode device status, or decode --components-json")
    status.add_argument("--components-json", help="Decode a local components JSON file instead of cloud fetch")
    status.set_defaults(func=command_status)

    decode = sub.add_parser("decode-file", help="Decode a saved components JSON file")
    decode.add_argument("components_json")
    decode.set_defaults(func=command_decode_file)

    write = sub.add_parser("write-component", help="Safely write a confirmed component; dry-run unless --yes")
    write.add_argument("component_id", type=int)
    write.add_argument("raw_value", type=int)
    write.add_argument("--yes", action="store_true")
    write.set_defaults(func=command_write)

    power = sub.add_parser("set-power", help="Set heat-pump power; dry-run unless --yes")
    power.add_argument("state", choices=["on", "off"])
    power.add_argument("--yes", action="store_true")
    power.set_defaults(func=command_set_power)

    mode = sub.add_parser("set-mode", help="Set mode/preset; dry-run unless --yes")
    mode.add_argument("mode", help="Mode name/alias or 0..6")
    mode.add_argument("--yes", action="store_true")
    mode.set_defaults(func=command_set_mode)

    setpoint = sub.add_parser("set-setpoint", help="Set target temperature in Celsius; dry-run unless --yes")
    setpoint.add_argument("temperature_c", type=float)
    setpoint.add_argument("--yes", action="store_true")
    setpoint.set_defaults(func=command_set_setpoint)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FluidraCloudError as err:
        print_json({"ok": False, "error": str(err)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
