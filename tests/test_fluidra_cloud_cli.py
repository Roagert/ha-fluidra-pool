"""Tests for the standalone Fluidra cloud CLI helpers."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_cloud_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "fluidra_cloud.py"
    spec = importlib.util.spec_from_file_location("fluidra_cloud", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_normalize_components_accepts_fluidra_list():
    cli = load_cloud_module()
    components = cli.normalize_components([
        {"id": 13, "reportedValue": 1},
        {"id": 15, "reportedValue": 240},
    ])

    assert components[13]["reportedValue"] == 1
    assert components[15]["reportedValue"] == 240


def test_decode_heatpump_status_uses_confirmed_amt_components():
    cli = load_cloud_module()
    status = cli.decode_heatpump_status([
        {"id": 0, "reportedValue": 409},
        {"id": 1, "reportedValue": -88},
        {"id": 2, "reportedValue": "192.168.1.29"},
        {"id": 3, "reportedValue": "LG24440781"},
        {"id": 4, "reportedValue": "2.5.0"},
        {"id": 5, "reportedValue": "amt"},
        {"id": 7, "reportedValue": "BXWAB0603494724050"},
        {"id": 11, "reportedValue": 1},
        {"id": 13, "reportedValue": 1},
        {"id": 14, "reportedValue": 2},
        {"id": 15, "reportedValue": 240},
        {"id": 17, "reportedValue": 0},
        {"id": 19, "reportedValue": 128},
        {"id": 28, "reportedValue": 0},
        {"id": 67, "reportedValue": 89},
        {"id": 68, "reportedValue": 128},
        {"id": 69, "reportedValue": 129},
        {"id": 74, "reportedValue": 224},
        {"id": 80, "reportedValue": 2},
        {"id": 81, "reportedValue": 7},
        {"id": 82, "reportedValue": 40},
    ])

    assert status["device_id"] == "LG24440781"
    assert status["thing_type"] == "amt"
    assert status["signature"].startswith("BXWAB")
    assert status["power"] == "on"
    assert status["mode"] == "smart-heating-cooling"
    assert status["set_temperature_c"] == 24.0
    assert status["water_temperature_c"] == 12.8
    assert status["air_temperature_c"] == 8.9
    assert status["water_outlet_temperature_c"] == 12.9
    assert status["no_flow"] is False
    assert status["status"] == "ok"
    assert status["min_setpoint_c"] == 7
    assert status["max_setpoint_c"] == 40


def test_mode_aliases_and_setpoint_conversion():
    cli = load_cloud_module()

    assert cli.raw_mode("boost-heating") == 3
    assert cli.raw_mode("auto") == 2
    assert cli.raw_mode("6") == 6
    assert cli.raw_setpoint_from_celsius(24.4) == 244


def test_validate_write_is_conservative():
    cli = load_cloud_module()

    assert cli.validate_write(13, 1) == []
    assert cli.validate_write(14, 0) == []
    assert cli.validate_write(15, 70) == []
    assert cli.validate_write(15, 400) == []
    assert cli.validate_write(15, 69)
    assert cli.validate_write(28, 1)


def test_dry_run_write_cli_does_not_need_credentials(capsys):
    cli = load_cloud_module()

    rc = cli.main(["set-setpoint", "25"])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["dry_run"] is True
    assert out["request"]["component_id"] == 15
    assert out["request"]["desiredValue"] == 250
