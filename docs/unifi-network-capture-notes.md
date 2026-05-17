# UniFi / local network capture notes

Date: 2026-05-17

Goal: find a correct capture point for `LG24440781` / `192.168.1.29` heat-pump traffic. A normal laptop Wi‑Fi capture cannot see heatpump↔cloud unicast traffic, so capture must run on the AP/router/switch path.

## Observed topology

Workstation:

```text
192.168.1.62 on wlp9s0
SSID: wifi-home
current BSSID: 16:ea:14:2a:e2:a7
```

Gateway/router:

```text
192.168.1.1
MAC: 90:f8:91:84:49:b3
Vendor: Kaonmedia / Orange Livebox
HTTP/HTTPS management present; not UniFi Network API
```

Managed switch:

```text
192.168.1.253
hostname: gs1920.home
MAC: e4:18:6b:f9:02:78
Vendor: Zyxel GS1920
HTTP/HTTPS/SSH present
```

Likely UniFi AP:

```text
192.168.1.55
MAC: 0c:ea:14:2a:e2:a5
SSH: open, Dropbear
BSSID family observed by nmcli:
  0c:ea:14:2a:e2:a6  wifi-home, channel 1
  16:ea:14:2a:e2:a6  wifi-home-appliances, channel 1
  16:ea:14:2a:e2:a7  wifi-home, channel 48  # workstation associated here
  1a:ea:14:2a:e2:a7  wifi-home_0p5, channel 48
  0c:ea:14:2a:e2:a8 / 12:ea:14:2a:e2:a8 / 16:ea:14:2a:e2:a8 on channel 37
```

Heat pump:

```text
192.168.1.29
MAC: ac:15:18:98:15:f0
```

## Access status

`192.168.1.55` is the best capture target if the heat pump is associated to this UniFi AP. SSH is reachable, but device credentials are required.

A single default credential check was attempted and failed:

```text
ubnt/ubnt: denied
root/ubnt: denied
admin/ubnt: denied
```

No brute forcing should be done. Use UniFi device SSH credentials from UniFi Network settings, or enable temporary SSH access.

## Best capture command once AP SSH credentials are available

Run from the workstation, replacing `<user>` with the UniFi AP SSH user:

```bash
ssh -o StrictHostKeyChecking=no <user>@192.168.1.55 \
  "tcpdump -i br0 -nn -s0 -U -w - 'host 192.168.1.29'" \
  > captures/fluidra-unifi-ap.pcap
```

If `br0` is not valid on this AP, inspect interfaces first:

```bash
ssh <user>@192.168.1.55 'ip -br link; ifconfig -a'
```

Likely alternatives:

```bash
tcpdump -i any -nn -s0 -U -w - 'host 192.168.1.29'
tcpdump -i br0 -nn -s0 -U -w - 'host 192.168.1.29'
tcpdump -i ath0 -nn -s0 -U -w - 'host 192.168.1.29'
tcpdump -i wlan0 -nn -s0 -U -w - 'host 192.168.1.29'
```

## Capture sequence

1. Start AP capture.
2. Run `python scripts/fluidra_cloud.py status` to record baseline.
3. Run a deliberate cloud write if safe, e.g. setpoint +1 °C with `--yes`, or use official iAquaLink+ app.
4. Restore setpoint.
5. Stop capture.
6. Analyze cloud endpoints/protocols:

```bash
tcpdump -nn -r captures/fluidra-unifi-ap.pcap
```

Useful filters after capture:

```bash
# all DNS involving heat pump if visible
tcpdump -nn -r captures/fluidra-unifi-ap.pcap 'host 192.168.1.29 and port 53'

# TLS/MQTT-ish traffic
tcpdump -nn -r captures/fluidra-unifi-ap.pcap 'host 192.168.1.29 and (tcp port 443 or tcp port 8883 or tcp port 8884)'

# any local UDP
tcpdump -nn -r captures/fluidra-unifi-ap.pcap 'host 192.168.1.29 and udp'
```

## Alternative: Zyxel GS1920 mirror

If AP SSH is not available, configure a temporary mirror/SPAN on `gs1920.home` (`192.168.1.253`) for the AP uplink port to a wired capture port. Then capture on the wired workstation/NIC. This requires Zyxel admin access and knowing the AP uplink port.
