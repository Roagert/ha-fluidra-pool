#!/usr/bin/env python3
"""Fluidra local CLI.

Read-only first tooling for Thomas's Fluidra/Amitime heat pump.

The CLI deliberately separates three concerns:

* local discovery: ping/TCP/MQTT CONNACK probes only;
* datapoint decoding: shared heat-pump component model;
* internet isolation planning: generate router/firewall commands, but never run them.

No command in this file publishes MQTT, sends UDP control frames, writes BLE
characteristics, or changes heat-pump settings. Future write support should stay
dry-run by default and require explicit confirmation.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_HOST = "192.168.1.11"
DEFAULT_MQTT_PORT = 1883
DEFAULT_TIMEOUT = 1.5

MODE_NAMES = {
    0: "SmartHeat",
    1: "SmartCool",
    2: "SmartAuto",
    3: "BoostHeat",
    4: "SilenceHeat",
    5: "BoostCool",
    6: "SilenceCool",
}

POWER_COMPONENT = 13
MODE_COMPONENT = 14
SETPOINT_COMPONENT = 15
RUNNING_COMPONENT = 11
WATER_TEMP_COMPONENT = 19
AMBIENT_TEMP_COMPONENT = 62
EXTRA_TEMP_COMPONENTS = tuple(range(65, 71))
FLOW_ERROR_CODES = {"E001", "E016"}

SAFE_WRITE_RANGES = {
    POWER_COMPONENT: (0, 1),
    MODE_COMPONENT: (0, 6),
    SETPOINT_COMPONENT: (150, 420),  # 15.0-42.0 °C raw x0.1
}

MQTT_311_RETURN_CODES = {
    0: "Connection accepted",
    1: "Connection refused: unacceptable protocol version",
    2: "Connection refused: identifier rejected",
    3: "Connection refused: server unavailable",
    4: "Connection refused: bad user name or password",
    5: "Connection refused: not authorized",
}

MQTT_5_REASON_CODES = {
    0x00: "Success",
    0x80: "Unspecified error",
    0x84: "Unsupported protocol version",
    0x85: "Client identifier not valid",
    0x86: "Bad user name or password",
    0x87: "Not authorized",
    0x88: "Server unavailable",
    0x8C: "Bad authentication method",
}


@dataclass(frozen=True)
class MqttConnack:
    """Decoded MQTT CONNACK result."""

    ok: bool
    protocol: str
    code: int
    message: str
    raw_hex: str


@dataclass(frozen=True)
class FirewallPlan:
    """Offline-only firewall/router plan for isolating the heat pump."""

    target_ip: str
    target_mac: str | None
    router: str
    lan_cidr: str
    commands: list[str]
    notes: list[str]
    safety_note: str


def _encode_utf8_field(value: str) -> bytes:
    data = value.encode("utf-8")
    if len(data) > 65535:
        raise ValueError("MQTT string field is too long")
    return len(data).to_bytes(2, "big") + data


def _encode_remaining_length(length: int) -> bytes:
    if length < 0:
        raise ValueError("length must be positive")
    encoded = bytearray()
    while True:
        digit = length % 128
        length //= 128
        if length > 0:
            digit |= 0x80
        encoded.append(digit)
        if length == 0:
            return bytes(encoded)


def build_mqtt_connect_packet(
    *,
    client_id: str = "fluidra-local-probe",
    username: str | None = None,
    password: str | None = None,
    mqtt5: bool = False,
) -> bytes:
    """Build a minimal MQTT CONNECT packet for safe CONNACK probing."""

    protocol_level = 5 if mqtt5 else 4
    flags = 0b0000_0010  # clean session / clean start
    payload = _encode_utf8_field(client_id)

    if username is not None:
        flags |= 0b1000_0000
    if password is not None:
        flags |= 0b0100_0000

    if username is not None:
        payload += _encode_utf8_field(username)
    if password is not None:
        payload += _encode_utf8_field(password)

    variable_header = _encode_utf8_field("MQTT") + bytes([protocol_level, flags]) + (30).to_bytes(2, "big")
    if mqtt5:
        variable_header += b"\x00"  # properties length

    remaining = variable_header + payload
    return b"\x10" + _encode_remaining_length(len(remaining)) + remaining


def parse_mqtt_connack(packet: bytes) -> MqttConnack:
    """Parse a minimal MQTT 3.1.1/5 CONNACK packet."""

    raw_hex = packet.hex()
    if len(packet) < 4 or packet[0] != 0x20:
        return MqttConnack(False, "unknown", -1, "Not an MQTT CONNACK packet", raw_hex)

    # MQTT 3.1.1 CONNACK: 20 02 <ack-flags> <return-code>
    if len(packet) == 4 and packet[1] == 0x02:
        code = packet[3]
        msg = MQTT_311_RETURN_CODES.get(code, f"Unknown MQTT 3.1.1 return code {code}")
        return MqttConnack(code == 0, "MQTT 3.1.1", code, msg, raw_hex)

    # MQTT 5 CONNACK: 20 <remaining-len> <ack-flags> <reason-code> <properties...>
    if len(packet) >= 5:
        code = packet[3]
        msg = MQTT_5_REASON_CODES.get(code, f"Unknown MQTT 5 reason code 0x{code:02x}")
        return MqttConnack(code == 0, "MQTT 5", code, msg, raw_hex)

    return MqttConnack(False, "unknown", -1, "Incomplete CONNACK packet", raw_hex)


def mqtt_connack_probe(
    host: str,
    port: int = DEFAULT_MQTT_PORT,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    client_id: str = "fluidra-local-probe",
    username: str | None = None,
    password: str | None = None,
    mqtt5: bool = False,
) -> MqttConnack:
    """Connect to a broker, send CONNECT, read CONNACK, then disconnect."""

    packet = build_mqtt_connect_packet(
        client_id=client_id,
        username=username,
        password=password,
        mqtt5=mqtt5,
    )
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(packet)
        data = sock.recv(8)
    return parse_mqtt_connack(data)


def tcp_connect_probe(host: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """Return True when a TCP connect succeeds."""

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ping_host(host: str, timeout_seconds: int = 2) -> bool:
    """Best-effort ICMP ping using the system ping command."""

    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout_seconds), host],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except OSError:
        return False


def _component_value(component: Any) -> Any:
    if isinstance(component, Mapping):
        if "reportedValue" in component:
            return component.get("reportedValue")
        if "reported" in component:
            return component.get("reported")
        if "value" in component:
            return component.get("value")
    return component


def _get_component(components: Mapping[Any, Any], component_id: int) -> Any:
    for key in (component_id, str(component_id)):
        if key in components:
            return _component_value(components[key])
    return None


def _raw_to_celsius(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value) / 10.0, 1)
    except (TypeError, ValueError):
        return None


def decode_heatpump_status(components: Mapping[Any, Any]) -> dict[str, Any]:
    """Decode known Amitime/Fluidra heat-pump components into friendly fields."""

    power_raw = _get_component(components, POWER_COMPONENT)
    mode_raw = _get_component(components, MODE_COMPONENT)
    running_raw = _get_component(components, RUNNING_COMPONENT)
    status: dict[str, Any] = {
        "power": "ON" if power_raw == 1 else "OFF" if power_raw == 0 else "unknown",
        "power_raw": power_raw,
        "mode": MODE_NAMES.get(mode_raw, "unknown"),
        "mode_raw": mode_raw,
        "running": bool(running_raw) if running_raw is not None else None,
        "running_raw": running_raw,
        "set_temperature_c": _raw_to_celsius(_get_component(components, SETPOINT_COMPONENT)),
        "water_temperature_c": _raw_to_celsius(_get_component(components, WATER_TEMP_COMPONENT)),
        "ambient_temperature_c": _raw_to_celsius(_get_component(components, AMBIENT_TEMP_COMPONENT)),
        "extra_temperatures_c": {},
        "flow_status": "unknown",
        "flow_note": "No numeric flow-rate datapoint is confirmed yet; infer no-flow from E001/E016 alarms.",
    }

    for cid in EXTRA_TEMP_COMPONENTS:
        value = _raw_to_celsius(_get_component(components, cid))
        if value is not None:
            status["extra_temperatures_c"][str(cid)] = value

    errors = extract_error_codes(components)
    status["errors"] = sorted(errors)
    if errors & FLOW_ERROR_CODES:
        status["flow_status"] = "no-flow-alarm"
    elif errors:
        status["flow_status"] = "no-flow-not-detected"
    return status


def extract_error_codes(components: Mapping[Any, Any]) -> set[str]:
    """Best-effort extraction of E/W error codes from component values."""

    found: set[str] = set()
    for item in components.values():
        values: Iterable[Any]
        if isinstance(item, Mapping):
            values = item.values()
        else:
            values = (item,)
        for value in values:
            if isinstance(value, str):
                for token in value.replace(",", " ").replace(";", " ").split():
                    token = token.strip().upper()
                    if len(token) == 4 and token[0] in {"E", "W"} and token[1:].isdigit():
                        found.add(token)
    return found


def validate_write(component_id: int, raw_value: int) -> list[str]:
    """Validate a future write against the confirmed safe component/range set."""

    if component_id not in SAFE_WRITE_RANGES:
        return [
            f"component {component_id} is not in the confirmed safe write set "
            f"{sorted(SAFE_WRITE_RANGES)}"
        ]
    minimum, maximum = SAFE_WRITE_RANGES[component_id]
    if not minimum <= raw_value <= maximum:
        return [f"component {component_id} value {raw_value} is outside {minimum}..{maximum}"]
    return []


def load_components_json(path: str | Path) -> dict[Any, Any]:
    """Load a component map/list from a JSON file."""

    data = json.loads(Path(path).read_text())
    if isinstance(data, Mapping):
        # Accept raw {"components": [...]}, debug dumps, or direct component maps.
        for key in ("components", "records", "items", "data"):
            value = data.get(key)
            if isinstance(value, (list, dict)):
                return normalize_components(value)
        if "device_components_data" in data and isinstance(data["device_components_data"], Mapping):
            first = next(iter(data["device_components_data"].values()), {})
            return normalize_components(first)
        return dict(data)
    if isinstance(data, list):
        return normalize_components(data)
    raise ValueError(f"Unsupported JSON shape in {path}")


def normalize_components(raw: Any) -> dict[Any, Any]:
    """Normalize list/dict component shapes to id->payload."""

    if isinstance(raw, Mapping):
        return dict(raw)
    result: dict[Any, Any] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            cid = item.get("id") or item.get("componentId") or item.get("componentID")
            if cid is not None:
                result[int(cid) if str(cid).isdigit() else cid] = dict(item)
    return result


def build_firewall_plan(
    *,
    target_ip: str,
    target_mac: str | None = None,
    router: str = "openwrt",
    lan_cidr: str = "192.168.1.0/24",
) -> FirewallPlan:
    """Generate a safe, offline-only plan to block internet while keeping LAN."""

    # Validate early so generated commands are well-formed.
    ipaddress.ip_address(target_ip)
    ipaddress.ip_network(lan_cidr, strict=False)

    safety_note = (
        "This CLI does not run these commands. Apply them on the router only "
        "after you confirm the heat pump remains reachable locally. Keep a rollback path."
    )
    notes = [
        "Goal: deny heat-pump traffic from LAN to WAN while preserving LAN access.",
        "Keep local MQTT available from Home Assistant/Nemo: allow LAN clients to reach tcp dport 1883 on the heat pump.",
        "Give the heat pump a DHCP reservation first so the IP/MAC cannot drift.",
        "After blocking WAN, verify: ping 192.168.1.11 and MQTT CONNACK still work locally.",
    ]

    router = router.lower()
    if router == "openwrt":
        commands = [
            f"uci add firewall rule",
            f"uci set firewall.@rule[-1].name='Block Fluidra heatpump WAN'",
            f"uci set firewall.@rule[-1].src='lan'",
            f"uci set firewall.@rule[-1].src_ip='{target_ip}'",
            f"uci set firewall.@rule[-1].dest='wan'",
            f"uci set firewall.@rule[-1].proto='all'",
            f"uci set firewall.@rule[-1].target='REJECT'",
            "uci commit firewall",
            "/etc/init.d/firewall reload",
            f"# nft equivalent: nft add rule inet fw4 forward ip saddr {target_ip} oifname @wan_devices reject",
        ]
        if target_mac:
            notes.append(f"DHCP reservation target MAC: {target_mac}")
    elif router in {"nft", "nftables"}:
        commands = [
            "nft add table inet fluidra_local",
            "nft 'add chain inet fluidra_local forward { type filter hook forward priority 0; policy accept; }'",
            f"nft add rule inet fluidra_local forward ip saddr {target_ip} ip daddr {lan_cidr} accept",
            f"nft add rule inet fluidra_local forward ip saddr {target_ip} reject",
        ]
    elif router in {"iptables", "linux"}:
        commands = [
            f"iptables -I FORWARD -s {target_ip} -d {lan_cidr} -j ACCEPT",
            f"iptables -I FORWARD -s {target_ip} ! -d {lan_cidr} -j REJECT",
            f"# rollback: iptables -D FORWARD -s {target_ip} ! -d {lan_cidr} -j REJECT",
            f"# rollback: iptables -D FORWARD -s {target_ip} -d {lan_cidr} -j ACCEPT",
        ]
    elif router in {"unifi", "ubiquiti"}:
        commands = [
            "UniFi UI: Settings → Security → Traffic & Firewall Rules → Create Entry",
            f"Action: Block / Reject; Source: IP Address {target_ip}; Destination: Internet; Schedule: Always",
            "Place rule above general allow rules. Do not block LAN/VLAN local traffic.",
        ]
    else:
        commands = [
            f"Create router rule: REJECT traffic from source {target_ip} to WAN/Internet.",
            f"Do not block source {target_ip} to LAN {lan_cidr}; keep tcp dport 1883 reachable from Home Assistant/Nemo.",
        ]

    return FirewallPlan(
        target_ip=target_ip,
        target_mac=target_mac,
        router=router,
        lan_cidr=lan_cidr,
        commands=commands,
        notes=notes,
        safety_note=safety_note,
    )


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def command_discover(args: argparse.Namespace) -> int:
    ports = args.ports or [80, 443, 1883, 8883, 8080, 8443, 9003, 8902, 5781, 5750, 1800, 1801, 3317, 3844]
    result: dict[str, Any] = {
        "host": args.host,
        "ping": ping_host(args.host),
        "tcp": {},
        "mqtt": None,
        "safe": "read-only: no publishes, no UDP control packets, no BLE writes",
    }
    for port in ports:
        result["tcp"][str(port)] = "open" if tcp_connect_probe(args.host, port, args.timeout) else "closed"
    if result["tcp"].get(str(args.mqtt_port)) == "open":
        result["mqtt"] = asdict(mqtt_connack_probe(args.host, args.mqtt_port, timeout=args.timeout, mqtt5=args.mqtt5))
    print_json(result)
    return 0


def command_mqtt_probe(args: argparse.Namespace) -> int:
    connack = mqtt_connack_probe(
        args.host,
        args.port,
        timeout=args.timeout,
        client_id=args.client_id,
        username=args.username,
        password=args.password,
        mqtt5=args.mqtt5,
    )
    print_json(asdict(connack))
    return 0 if connack.ok else 2


def command_status(args: argparse.Namespace) -> int:
    components = load_components_json(args.components_json)
    print_json(decode_heatpump_status(components))
    return 0


def command_firewall_plan(args: argparse.Namespace) -> int:
    plan = build_firewall_plan(
        target_ip=args.host,
        target_mac=args.mac,
        router=args.router,
        lan_cidr=args.lan_cidr,
    )
    if args.format == "json":
        print_json(asdict(plan))
    else:
        print(f"# Fluidra internet-isolation plan for {plan.target_ip}\n")
        print(plan.safety_note)
        print("\n## Notes")
        for note in plan.notes:
            print(f"- {note}")
        print("\n## Commands / router steps")
        for command in plan.commands:
            print(command)
    return 0


def command_validate_write(args: argparse.Namespace) -> int:
    errors = validate_write(args.component_id, args.raw_value)
    print_json({"ok": not errors, "errors": errors})
    return 0 if not errors else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fluidra local read-only CLI and internet-isolation planner")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Heat-pump LAN IP (default: {DEFAULT_HOST})")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="Read-only LAN/TCP/MQTT discovery")
    discover.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    discover.add_argument("--mqtt-port", type=int, default=DEFAULT_MQTT_PORT)
    discover.add_argument("--mqtt5", action="store_true", help="Probe MQTT 5 instead of MQTT 3.1.1")
    discover.add_argument("--ports", type=int, nargs="*", help="TCP ports to probe")
    discover.set_defaults(func=command_discover)

    mqtt = sub.add_parser("mqtt-probe", help="Send MQTT CONNECT and print CONNACK; no subscribe/publish")
    mqtt.add_argument("--port", type=int, default=DEFAULT_MQTT_PORT)
    mqtt.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    mqtt.add_argument("--client-id", default="fluidra-local-probe")
    mqtt.add_argument("--username")
    mqtt.add_argument("--password")
    mqtt.add_argument("--mqtt5", action="store_true")
    mqtt.set_defaults(func=command_mqtt_probe)

    status = sub.add_parser("status", help="Decode a local/cloud component JSON file into heat-pump status")
    status.add_argument("components_json", help="JSON file containing component map/list")
    status.set_defaults(func=command_status)

    fw = sub.add_parser("firewall-plan", help="Generate router/firewall steps to block heat-pump internet access")
    fw.add_argument("--mac", help="Heat-pump MAC for notes/DHCP reservation")
    fw.add_argument("--router", default="openwrt", choices=["openwrt", "nft", "nftables", "iptables", "linux", "unifi", "ubiquiti", "generic"])
    fw.add_argument("--lan-cidr", default="192.168.1.0/24")
    fw.add_argument("--format", choices=["text", "json"], default="text")
    fw.set_defaults(func=command_firewall_plan)

    vw = sub.add_parser("validate-write", help="Validate future write against safe component/range allow-list")
    vw.add_argument("component_id", type=int)
    vw.add_argument("raw_value", type=int)
    vw.set_defaults(func=command_validate_write)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
