# Fluidra Local CLI

`fluidra_local.py` is a standalone, read-only-first CLI for investigating and eventually operating the Fluidra/Amitime heat pump locally.

Current target:

- Device: `LG24440781`
- LAN IP: `192.168.1.11`
- Confirmed local service: MQTT on `tcp/1883`, authentication required

## Safety model

The CLI currently does **not**:

- publish MQTT messages
- send UDP control packets
- write BLE characteristics
- change heat-pump settings
- apply firewall/router rules

It can safely:

- probe LAN reachability and TCP ports
- send MQTT `CONNECT` and decode `CONNACK`
- decode component JSON into friendly heat-pump status
- validate whether a future write would be inside the confirmed safe component/range set
- generate router/firewall instructions to block internet access while preserving LAN access

## Usage

From the repository root:

```bash
python3 scripts/fluidra_local.py --host 192.168.1.11 discover
```

Probe only MQTT:

```bash
python3 scripts/fluidra_local.py --host 192.168.1.11 mqtt-probe
python3 scripts/fluidra_local.py --host 192.168.1.11 mqtt-probe --mqtt5
```

Decode a component JSON dump:

```bash
python3 scripts/fluidra_local.py status components.json
```

Validate a future write without sending it:

```bash
python3 scripts/fluidra_local.py validate-write 13 1     # power ON
python3 scripts/fluidra_local.py validate-write 14 2     # SmartAuto
python3 scripts/fluidra_local.py validate-write 15 290   # 29.0 °C
```

Generate an internet-isolation plan:

```bash
python3 scripts/fluidra_local.py --host 192.168.1.11 firewall-plan \
  --mac 02:0e:8a:69:3d:61 \
  --router openwrt \
  --lan-cidr 192.168.1.0/24
```

The firewall plan is intentionally output-only. Apply it on the router only after confirming the heat pump remains reachable locally.

## Confirmed datapoints

- `13`: power, `0=OFF`, `1=ON`
- `14`: mode
  - `0` SmartHeat
  - `1` SmartCool
  - `2` SmartAuto
  - `3` BoostHeat
  - `4` SilenceHeat
  - `5` BoostCool
  - `6` SilenceCool
- `15`: set temperature, raw `x0.1 °C`
- `19`: water temperature, raw `x0.1 °C`
- `62`: ambient/outdoor temperature, raw `x0.1 °C`
- `65..70`: additional temperature sensors, raw `x0.1 °C`
- `11`: running/active state

No numeric flow-rate datapoint is confirmed yet. Flow is currently inferred from no-flow style alarm codes such as `E001` and `E016`.

## Local-only / disconnect-from-web plan

The practical way to disconnect the Fluidra device from the web while keeping local control is router-level egress blocking:

1. Give the heat pump a DHCP reservation by MAC address.
2. Block traffic from the heat-pump IP/MAC to WAN/Internet.
3. Keep LAN traffic allowed, especially Home Assistant/Nemo → heat pump `tcp/1883`.
4. Verify local MQTT still answers `CONNACK`.
5. Only then proceed with local MQTT credential/topic discovery.

Use `firewall-plan` to generate commands/steps for OpenWrt, nftables, iptables, UniFi, or a generic router.

## Current blocker

Local MQTT requires authentication. The next implementation step is extracting or discovering the local MQTT username/password/topic scheme from redacted cloud device detail/uiconfig/command-control objects or passive traffic capture.
