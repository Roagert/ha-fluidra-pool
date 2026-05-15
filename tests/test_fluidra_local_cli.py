"""Tests for the standalone Fluidra local CLI helpers."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_cli_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "fluidra_local.py"
    spec = importlib.util.spec_from_file_location("fluidra_local", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_mqtt_connack_rejects_not_authorized_v311():
    cli = load_cli_module()

    result = cli.parse_mqtt_connack(bytes.fromhex("20020005"))

    assert result.ok is False
    assert result.protocol == "MQTT 3.1.1"
    assert result.code == 5
    assert "not authorized" in result.message.lower()


def test_build_firewall_plan_defaults_to_openwrt_and_preserves_lan_mqtt():
    cli = load_cli_module()

    plan = cli.build_firewall_plan(
        target_ip="192.168.1.11",
        target_mac="02:0e:8a:69:3d:61",
        router="openwrt",
        lan_cidr="192.168.1.0/24",
    )

    assert plan.target_ip == "192.168.1.11"
    assert any("REJECT" in command for command in plan.commands)
    assert any("192.168.1.11" in command for command in plan.commands)
    assert any("tcp dport 1883" in command or "--dport 1883" in command for command in plan.notes + plan.commands)
    assert "does not run these commands" in plan.safety_note.lower()


def test_decode_heatpump_status_converts_known_components():
    cli = load_cli_module()
    components = {
        11: {"reportedValue": 1},
        13: {"reportedValue": 1},
        14: {"reportedValue": 2},
        15: {"reportedValue": 290, "desiredValue": 290},
        19: {"reportedValue": 131},
        62: {"reportedValue": 87},
    }

    status = cli.decode_heatpump_status(components)

    assert status["power"] == "ON"
    assert status["mode"] == "SmartAuto"
    assert status["set_temperature_c"] == 29.0
    assert status["water_temperature_c"] == 13.1
    assert status["ambient_temperature_c"] == 8.7
    assert status["running"] is True


def test_safe_write_validation_allows_only_confirmed_controls():
    cli = load_cli_module()

    assert cli.validate_write(13, 1) == []
    assert cli.validate_write(14, 6) == []
    assert cli.validate_write(15, 420) == []
    assert cli.validate_write(15, 149)
    assert cli.validate_write(62, 120)
