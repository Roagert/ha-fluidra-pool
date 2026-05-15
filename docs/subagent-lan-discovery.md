# Subagent LAN Discovery — Fluidra/Amitime heat pump

Date: 2026-05-15T18:29:47+02:00
Target: `192.168.1.11` (`LG24440781`, `amt`, firmware `2.5.0`)
Scope: local read-only connectivity discovery only. No setting changes, no PUT/control packets, no MQTT publishes.

## Summary

The heat pump is reachable from this host on the same LAN. A conservative TCP scan found exactly one open TCP service: MQTT on `tcp/1883`. Common HTTP/HTTPS/alternative HTTP ports were closed/refused, so there were no local HTTP endpoints to query. UDP candidate ports mostly returned ICMP port-unreachable or no response to a single zero-length probe; there was no readable UDP response.

Anonymous MQTT read-only probing reached the broker but authentication is required:

- MQTT 3.1.1 anonymous `CONNECT`: CONNACK return code `5` (`Not authorized`).
- MQTT 5 anonymous `CONNECT`: CONNACK reason code `0x87` (`Not authorized`).
- Because the broker refused anonymous connection, no subscription/read of topics was possible without credentials.

## Commands run and evidence

### Reachability

```bash
ping -c 3 -W 2 192.168.1.11
ip route get 192.168.1.11
ip neigh show 192.168.1.11
```

Result:

```text
3 packets transmitted, 3 received, 0% packet loss
rtt min/avg/max/mdev = 1.299/2.380/4.175/1.278 ms
192.168.1.11 dev wlp9s0 src 192.168.1.62 uid 1000
192.168.1.11 dev wlp9s0 lladdr 02:0e:8a:69:3d:61 REACHABLE
```

### Tool availability

```bash
command -v nmap || true
command -v nc || true
command -v curl || true
```

Result: `nmap` was not installed. `nc` and `curl` were installed.

### TCP connect scan

Since `nmap` was unavailable, a small Python TCP connect scan was used with an 0.8s timeout against likely Fluidra/Amitime and common IoT/HTTP ports:

```text
22,23,53,80,81,443,502,1883,3317,3844,5750,5781,8000,8080,8443,8883,8888,8902,9003,1800,1801
```

Result:

```text
closed tcp/22 refused
closed tcp/23 refused
closed tcp/53 refused
closed tcp/80 refused
closed tcp/81 refused
closed tcp/443 refused
closed tcp/502 refused
OPEN tcp/1883
closed tcp/3317 refused
closed tcp/3844 refused
closed tcp/5750 refused
closed tcp/5781 refused
closed tcp/8000 refused
closed tcp/8080 refused
closed tcp/8443 refused
closed tcp/8883 refused
closed tcp/8888 refused
closed tcp/8902 refused
closed tcp/9003 refused
closed tcp/1800 refused
closed tcp/1801 refused
```

### UDP zero-length probes

One zero-length UDP datagram was sent per candidate port, then the socket waited for a response/ICMP error with a 1s timeout. No control payloads were sent.

Ports:

```text
9003,8902,5781,5750,1800,1801,3317,3844,1883,80,8080
```

Result:

```text
closed udp/9003 icmp-port-unreachable
closed udp/8902 icmp-port-unreachable
closed udp/5781 icmp-port-unreachable
closed udp/5750 icmp-port-unreachable
closed udp/1800 icmp-port-unreachable
closed udp/1801 icmp-port-unreachable
no-response udp/3317
closed udp/3844 icmp-port-unreachable
no-response udp/1883
closed udp/80 icmp-port-unreachable
no-response udp/8080
```

Interpretation: no UDP service exposed a readable response to a no-payload probe. `no-response` does not prove closed/open because UDP services and firewalls often drop empty datagrams.

### MQTT read-only auth probe on tcp/1883

A minimal MQTT client was used to test anonymous read-only connectivity. It did not publish and did not send any device command topics.

MQTT 3.1.1 anonymous `CONNECT`:

```text
CONNACK/raw: 20020005 b' \\x02\\x00\\x05'
MQTT CONNECT refused return_code=5
```

MQTT 5 anonymous `CONNECT`:

```text
MQTT5 CONNACK/raw: 2003008700 b' \\x03\\x00\\x87\\x00'
MQTT5 reason_code: 135
```

Interpretation: local MQTT broker is present but requires authentication. No topics/status/datapoints could be read anonymously.

## Services identified

- `tcp/1883`: MQTT broker reachable, auth required, no anonymous readable status.
- No open local HTTP/HTTPS services found on tested ports (`80`, `81`, `443`, `8000`, `8080`, `8443`, `8888`).
- `tcp/9003`, `tcp/8902`, `tcp/5781`, `tcp/5750`, `tcp/1800`, `tcp/1801`, `tcp/3317`, `tcp/3844`: closed/refused.
- UDP candidates: no readable response; most explicitly ICMP-unreachable.

## Next step for CLI implementation

The best local CLI path is likely **authenticated local MQTT over `192.168.1.11:1883`**, not local HTTP and not the previously hypothesized iQBridge-style `tcp/udp 9003` path for this `amt` device.

Recommended next steps:

1. Retrieve/derive the MQTT credentials used by the heat pump/module. Candidate sources:
   - Cloud device detail / UI config / command-and-control object, if it exposes local MQTT auth material.
   - APK/Dart AOT strings around `MobileCommandAndControlLocalUdp`, `udpKey`, `sendUDPCommand`, and any MQTT credential generation paths.
   - Passive mobile-app traffic capture during normal app launch on Thomas's LAN, with secrets redacted in reports.
2. Once credentials are known, implement a read-only MQTT CLI probe:
   - `CONNECT` to `mqtt://192.168.1.11:1883` using discovered credentials.
   - Subscribe to a narrow set of candidate status topics first, then broader wildcard only briefly if needed.
   - Never publish until topic semantics are confirmed and user explicitly requests control support.
3. Keep cloud REST/WebSocket as the known-working fallback until authenticated local MQTT topics are mapped.

## If rerunning from Thomas's LAN

```bash
ping -c 3 -W 2 192.168.1.11
python3 - <<'PY'
import socket
host='192.168.1.11'
ports=[22,23,53,80,81,443,502,1883,3317,3844,5750,5781,8000,8080,8443,8883,8888,8902,9003,1800,1801]
for p in ports:
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM); s.settimeout(0.8)
    rc=s.connect_ex((host,p)); print(('OPEN' if rc==0 else 'closed/no-open'), 'tcp/%d' % p, 'errno=%s' % rc)
    s.close()
PY
```

Optional, if `mosquitto_sub` is installed and credentials are later known:

```bash
mosquitto_sub -h 192.168.1.11 -p 1883 -u '<username>' -P '<password>' -t '#' -v -C 20 -W 10
```

Do not use `mosquitto_pub` or send control topics until topic semantics are confirmed.
