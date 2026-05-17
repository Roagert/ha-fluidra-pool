# Fluidra UniFi AP capture — 2026-05-17

Goal: capture heat-pump traffic from the correct network vantage point instead of from the laptop Wi‑Fi client.

## Access path used

- Proxmox host: `192.168.1.100`, `pve-manager/9.1.4`
- UniFi controller container: LXC `105`, `unifi-os-server`, IP `192.168.1.66`
- Adopted UniFi AP: `U7PRO`, IP `192.168.1.55`, MAC `0c:ea:14:2a:e2:a5`, version `8.5.21.18681`
- Heat pump: `192.168.1.29`, MAC `ac:15:18:98:15:f0`, UniFi client hostname `Fluidra`

The UniFi controller database exposed device SSH credentials for the adopted AP. Credentials were used but not written to this repository.

## Capture command

Capture was run on the UniFi AP bridge, streamed back to this workstation:

```bash
tcpdump -i br0 -nn -s0 -U -w - 'host 192.168.1.29'
```

Output file:

```text
captures/fluidra-unifi-ap-20260517-091757.pcap
```

Tcpdump summary:

```text
8 packets captured
8 packets received by filter
0 packets dropped by kernel
```

## Cloud action during capture

The authenticated Fluidra cloud CLI was run while the AP capture was active:

1. `status` baseline
2. `set-setpoint 25.0 --yes`
3. wait ~8 seconds
4. `status`
5. `set-setpoint 24.0 --yes`
6. wait ~8 seconds
7. `status`

Status snippets:

```text
before:       setpoint 24.0 °C, water 12.0 °C, air 16.6 °C, power off
after +1:     setpoint 25.0 °C, water 12.0 °C, air 16.6 °C, power off
after restore:setpoint 24.0 °C, water 12.0 °C, air 16.6 °C, power off
```

Post-capture component check showed component `15` back at reported value `240`.

## Packets observed

```text
2026-05-17 09:18:07 IP 192.168.1.46.48150 > 192.168.1.29.80: SYN
2026-05-17 09:18:07 ARP who-has 192.168.1.46 tell 192.168.1.29
2026-05-17 09:18:07 ARP reply 192.168.1.46 is-at 20:37:f0:8c:74:a6
2026-05-17 09:18:07 IP 192.168.1.29.80 > 192.168.1.46.48150: RST,ACK
2026-05-17 09:18:12 ARP who-has 192.168.1.29 tell 192.168.1.46
2026-05-17 09:18:12 ARP reply 192.168.1.29 is-at ac:15:18:98:15:f0
2026-05-17 09:18:38 ARP who-has 192.168.1.29 tell 192.168.1.29
2026-05-17 09:19:38 ARP who-has 192.168.1.29 tell 192.168.1.29
```

Protocol counts:

```text
ARP: 6
IP/TCP-ish lines: 2
UDP: 0
ICMP: 0
```

## Interpretation

Confirmed:

- Proxmox access works.
- UniFi controller is reachable and identified the adopted AP.
- AP SSH access works via controller device credentials.
- AP bridge capture works and sees heat-pump LAN frames.
- During this 120-second capture, no heatpump↔cloud traffic appeared for `192.168.1.29` on `br0`.

Not yet proven:

- This does not prove the heat pump never talks to cloud. It may keep a long-lived connection with sparse traffic, or the relevant frames may be on a different AP interface/VLAN path.
- Because the heat pump power was `off`, changing setpoint may update cloud desired state without immediately causing much device traffic.

Recommended next capture:

- Capture longer on the AP, preferably 10–15 minutes.
- Use `-i any` as well as `-i br0` to catch AP-internal interface differences.
- During the capture, perform an action more likely to force device communication, e.g. power on briefly if safe, then restore.
