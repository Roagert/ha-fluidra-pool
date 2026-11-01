# Fluidra passive LAN capture during authenticated cloud CLI — 2026-05-17

Target: `LG24440781` / `192.168.1.29` / MAC `ac:15:18:98:15:f0`

Capture file on local workstation:

```text
captures/fluidra-cloudcli-passive-20260517-081358.pcap
```

Capture command:

```bash
sudo -n timeout 90 tcpdump -i any -nn -s0 -w captures/fluidra-cloudcli-passive-20260517-081358.pcap \
  'host 192.168.1.29 and (udp or arp or icmp)'
```

CLI commands executed while capture was running:

```bash
python scripts/fluidra_local.py --host 192.168.1.29 discover
python scripts/fluidra_cloud.py status
python scripts/fluidra_cloud.py components
python scripts/fluidra_cloud.py uiconfig
python scripts/fluidra_cloud.py set-setpoint 25
```

Safety notes:

- Cloud CLI used the saved token cache at `~/.cache/fluidra-cloud/token.json`.
- `set-setpoint 25` was dry-run only because `--yes` was not supplied.
- No unsafe cloud write, local UDP command, MQTT publish, or BLE write was sent.

## CLI result

Authenticated cloud reads succeeded from cache.

Decoded status during capture:

```text
device_id: LG24440781
thing_type: amt
signature: BXWAB0603494724050
status: ok
power: off
mode: smart-heating-cooling
set_temperature_c: 24.0
water_temperature_c: 11.8
air_temperature_c: 12.6
no_flow: false
supply_voltage_v: 222
wifi_rssi_dbm: -89
```

Component highlights:

```text
component_count: 83
c13: 0
c14: 2
c15: 240
c19: 118
c28: 0
c67: 126
c68: 118
c69: 118
c80: 2
c81: 7
c82: 40
```

## Packet summary

Protocol counts:

```text
ICMP: 2
ARP: 7
UDP: 0
```

Packets:

```text
2026-05-17 08:14:13.350214 wlp9s0 Out IP 192.168.1.62 > 192.168.1.29: ICMP echo request
2026-05-17 08:14:13.776641 wlp9s0 B   ARP, Request who-has 192.168.1.62 tell 192.168.1.29
2026-05-17 08:14:13.776659 wlp9s0 Out ARP, Reply 192.168.1.62 is-at 4c:82:a9:f0:83:8d
2026-05-17 08:14:13.776642 wlp9s0 B   ARP, Request who-has 192.168.1.62 tell 192.168.1.29
2026-05-17 08:14:13.776670 wlp9s0 Out ARP, Reply 192.168.1.62 is-at 4c:82:a9:f0:83:8d
2026-05-17 08:14:13.821611 wlp9s0 In  IP 192.168.1.29 > 192.168.1.62: ICMP echo reply
2026-05-17 08:14:18.517590 wlp9s0 Out ARP, Request who-has 192.168.1.29 tell 192.168.1.62
2026-05-17 08:14:18.602266 wlp9s0 In  ARP, Reply 192.168.1.29 is-at ac:15:18:98:15:f0
2026-05-17 08:14:38.971625 wlp9s0 B   ARP, Request who-has 192.168.1.29 tell 192.168.1.29
```

## Evidence result

Authenticated cloud CLI reads do not appear to trigger any visible LAN UDP exchange between this host and the heat pump. The only observed local traffic was ARP/ICMP from read-only discovery.

This still does not rule out local UDP for the official phone app, because the cloud CLI talks to `api.fluidra-emea.com`, not directly to the heat pump. The next decisive test remains a same-LAN phone-app capture while changing/restoring setpoint in iAquaLink+.
