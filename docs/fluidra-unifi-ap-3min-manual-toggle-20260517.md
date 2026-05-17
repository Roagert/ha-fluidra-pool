# Fluidra UniFi AP 3-minute manual-toggle capture — 2026-05-17

Capture target: `192.168.1.29` / `ac:15:18:98:15:f0`.

Capture point: UniFi U7 Pro AP at `192.168.1.55`, via SSH, interface `any`.

Command:

```bash
tcpdump -i any -nn -s0 -U -w - 'host 192.168.1.29'
```

Output file:

```text
captures/fluidra-unifi-ap-any-3min-20260517-093340.pcap
```

Duration: 180 seconds.

Tcpdump result:

```text
36 packets captured
38 packets received by filter
0 packets dropped by kernel
```

Observed packets:

```text
ARP: 36
UDP: 0
ICMP: 0
TCP/IP: 0
```

The packets were repeated ARP probes from/toward `192.168.1.29`, roughly once per minute. No DNS, TCP/TLS, MQTT, UDP, or other cloud traffic for the heat pump was visible on this AP during the 3-minute window.

Cloud status immediately after capture:

```text
power: off
power_raw: 0
running: true
setpoint: 22.0 °C
water: 12.0 °C
air: 14.6 °C
status: ok
supply voltage: 224 V
```

Interpretation:

- The AP capture path works.
- During this window, even after manual interaction, the AP saw only ARP for the heat pump.
- This suggests either the manual action did not require immediate cloud traffic, the heat pump maintains a very sparse/long-lived connection not active during the window, or the heat pump may be on another path/AP/interface despite UniFi stale client history.

Next evidence step:

- Identify the heat pump's live association/AP/radio from UniFi, or capture simultaneously on AP `br0`, `wifi0*`, `wifi1*`, `wifi2*`, and uplink `eth0` with no restrictive host filter for a short period and then filter offline.
