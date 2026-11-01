#!/usr/bin/env python3
"""Summarise a heat-pump capture (classic pcap or pcapng; stdlib only): peers, DNS, TLS SNI and
flags for local traffic. No payload bytes unless --payload. Runbook: docs/LOCAL_CAPTURE.md."""
import argparse
import ipaddress
import struct
from collections import Counter
from datetime import datetime, time
from pathlib import Path

LAN_NETS = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",          # RFC1918
    "169.254.0.0/16", "224.0.0.0/4", "255.255.255.255/32")]  # link-local, multicast, broadcast
INFRA_PORTS = {53, 67, 68}  # DNS/DHCP with the router: expected, listed but never flagged
MQTT_PORTS = {1883, 8883}
PROTOS = {1: "icmp", 2: "igmp", 6: "tcp", 17: "udp"}
QTYPES = {1: "A", 12: "PTR", 16: "TXT", 28: "AAAA", 33: "SRV"}
WINDOW = 5  # seconds listed around each --marks time
# linktype -> offsets of (src MAC, ethertype, IP header): Ethernet (tcpdump -i br0) and
# Linux cooked v1 / v2 (tcpdump -i any; these carry no destination MAC)
LINKS = {1: (6, 12, 14), 113: (6, 14, 16), 276: (12, 0, 20)}


def clock(ts, fmt="%H:%M:%S"):
    return datetime.fromtimestamp(ts).strftime(fmt)  # local time, like the times noted in the runbook


def read_packets(data):
    """Yield (epoch seconds, linktype, frame) from classic pcap or pcapng bytes."""
    if data[:4] == b"\x0a\x0d\x0d\x0a":
        yield from _pcapng(data)
        return
    e = "<" if data[2:4] == b"\xb2\xa1" else ">"
    magic = struct.unpack(e + "I", data[:4])[0] if len(data) >= 24 else 0
    if magic not in (0xA1B2C3D4, 0xA1B23C4D):  # microsecond / nanosecond timestamps
        raise SystemExit("not a pcap or pcapng file (empty capture?)")
    div, link = 1e6 if magic == 0xA1B2C3D4 else 1e9, struct.unpack(e + "I", data[20:24])[0]
    off = 24
    while off + 16 <= len(data):
        sec, frac, caplen, _ = struct.unpack(e + "4I", data[off:off + 16])
        yield sec + frac / div, link, data[off + 16:off + 16 + caplen]
        off += 16 + caplen


def _pcapng(data):
    off, e, ifaces = 0, "<", []
    while off + 12 <= len(data):
        btype = struct.unpack(e + "I", data[off:off + 4])[0]
        if btype == 0x0A0D0D0A:  # Section Header Block: its byte-order magic sets endianness
            e, ifaces = "<" if data[off + 8:off + 12] == b"\x4d\x3c\x2b\x1a" else ">", []
        blen = struct.unpack(e + "I", data[off + 4:off + 8])[0]
        body = data[off + 8:off + blen - 4]
        if btype == 1:  # Interface Description Block
            ifaces.append((struct.unpack(e + "H", body[:2])[0], _tsresol(body[8:], e)))
        elif btype == 6 and len(body) >= 20:  # Enhanced Packet Block
            iface, hi, lo, caplen = struct.unpack(e + "4I", body[:16])
            link, ticks = ifaces[iface]
            yield ((hi << 32) | lo) / ticks, link, body[20:20 + caplen]
        off += max(blen, 12)


def _tsresol(opts, e):
    """Timestamp ticks per second from the IDB if_tsresol option (default microseconds)."""
    while len(opts) >= 8:
        code, n = struct.unpack(e + "HH", opts[:4])
        if code == 9:
            return 2 ** (opts[4] & 0x7F) if opts[4] & 0x80 else 10 ** opts[4]
        opts = opts[4 + (n + 3) // 4 * 4:]
    return 10 ** 6


def dns_name(msg, off):
    """Return (name, offset after it). A compression pointer ends the name and is not followed:
    the first question never needs one and answer owner names are only skipped."""
    labels = []
    while msg[off] and msg[off] < 0xC0:
        labels.append(msg[off + 1:off + 1 + msg[off]].decode("ascii", "replace"))
        off += 1 + msg[off]
    return ".".join(labels), off + (2 if msg[off] else 1)


def parse_dns(msg):
    """Return (questions if msg is a query, [(qname, ipv4)] A answers)."""
    qd, an = struct.unpack(">HH", msg[4:8])
    off, qs, ans = 12, [], []
    for _ in range(qd):
        name, off = dns_name(msg, off)
        qs.append((struct.unpack(">H", msg[off:off + 2])[0], name))
        off += 4
    for _ in range(an):
        _, off = dns_name(msg, off)
        rtype, _, _, rdlen = struct.unpack(">HHIH", msg[off:off + 10])
        if rtype == 1 and rdlen == 4 and qs:
            ans.append((qs[0][1], str(ipaddress.IPv4Address(msg[off + 10:off + 14]))))
        off += 10 + rdlen
    return ([] if msg[2] & 0x80 else qs), ans


def tls_sni(p):
    """Server name from a TLS ClientHello. Only the first TCP segment is parsed (no reassembly):
    fine while server_name is in it (ESP32, OpenSSL); else struct.error -> counted undecodable."""
    if len(p) < 44 or p[0] != 0x16 or p[5] != 0x01:
        return None
    off = 44 + p[43]                                     # skip headers, version, random, session id
    off += 2 + struct.unpack(">H", p[off:off + 2])[0]    # cipher suites
    off += 1 + p[off]                                    # compression methods
    end, off = off + 2 + struct.unpack(">H", p[off:off + 2])[0], off + 2
    while off + 4 <= end:
        etype, elen = struct.unpack(">HH", p[off:off + 4])
        if etype == 0:  # server_name: list len(2), name type(1), name len(2), name
            n = struct.unpack(">H", p[off + 7:off + 9])[0]
            return p[off + 9:off + 9 + n].decode("ascii", "replace")
        off += 4 + elen
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Summarise a heat-pump pcap/pcapng capture.")
    ap.add_argument("capture", type=Path)
    ap.add_argument("--hp-ip", default="192.168.1.29")
    ap.add_argument("--hp-mac", default="ac:15:18:98:15:f0", type=lambda m: bytes.fromhex(m.replace(":", "")))
    ap.add_argument("--marks", default="", help="clock times HH:MM:SS[,...]: list packets ±5 s around each")
    ap.add_argument("--payload", action="store_true", help="append 64 payload bytes (hex) to --marks lines")
    args = ap.parse_args(argv)
    pkts = list(read_packets(args.capture.read_bytes()))
    day = datetime.fromtimestamp(pkts[0][0] if pkts else 0).date()  # marks are on the capture's day
    marks = {m: datetime.combine(day, time.fromisoformat(m)).timestamp() for m in args.marks.split(",") if m}
    non_ip = bad = 0
    peers = {}  # (proto, peer ip, port) -> [packets, bytes, first ts, last ts]
    queries, answers, snis, listed = Counter(), set(), set(), {m: [] for m in marks}

    for ts, link, frame in pkts:
        try:
            sm, et, l3 = LINKS.get(link, (0, 0, 0))
            if link not in LINKS or frame[et:et + 2] != b"\x08\x00":  # IPv4 only; the rest is counted
                non_ip += 1
                continue
            smac, dmac, ip = frame[sm:sm + 6], frame[:6] if link == 1 else None, frame[l3:]
            src, dst = (str(ipaddress.IPv4Address(ip[a:a + 4])) for a in (12, 16))
            out = src == args.hp_ip or smac == args.hp_mac
            if not (out or dst == args.hp_ip or dmac == args.hp_mac):
                continue
            proto, size = ip[9], struct.unpack(">H", ip[2:4])[0]
            l4 = ip[(ip[0] & 0x0F) * 4:size]
            sport, dport, port, data = None, None, None, b""
            if proto in (6, 17):
                sport, dport = struct.unpack(">HH", l4[:4])
                data = l4[(l4[12] >> 4) * 4:] if proto == 6 else l4[8:]
                port = min(sport, dport)  # the service port is almost always the lower one
            pname, peer = PROTOS.get(proto, str(proto)), dst if out else src
            s = peers.setdefault((pname, peer, port), [0, 0, ts, ts])
            s[0], s[1], s[3] = s[0] + 1, s[1] + size, ts
            for m in (m for m, mts in marks.items() if abs(ts - mts) <= WINDOW):
                a, b = (i if p is None else f"{i}:{p}" for i, p in ((src, sport), (dst, dport)))
                listed[m].append(f"  {clock(ts, '%H:%M:%S.%f')[:-3]}  {'out' if out else 'in '} {pname:4} "
                                 f"{a} -> {b}  {size} B" + (f"  {data[:64].hex()}" if args.payload else ""))
            if proto == 17 and port in (53, 5353):  # DNS and mDNS
                qs, ans = parse_dns(data)
                queries.update(qs)
                answers.update(ans)
            if proto == 6 and (sni := tls_sni(data)):
                snis.add((peer, sni))
        except (struct.error, IndexError, ValueError):
            bad += 1

    rows = sorted(peers.items(), key=lambda kv: -kv[1][1])
    names = {addr: q for q, addr in answers} | dict(snis)  # peer ip -> hostname
    print(f"{args.capture}: {len(pkts)} frames ({non_ip} not IPv4, {bad} undecodable), heat pump "
          f"{args.hp_ip} / {args.hp_mac.hex(':')}: {sum(s[0] for s in peers.values())} IPv4 packets")
    print("\nPeers (port = lower of the two ports; times = local clock)",
          f"  {'proto':5} {'peer':15} {'port':>5} {'pkts':>6} {'bytes':>8} {'first':8} {'last':8} name",
          *(f"  {p:5} {a:15} {'-' if pt is None else pt:>5} {n:>6} {b:>8} {clock(t0)} {clock(t1)} "
            f"{names.get(a, '')}".rstrip() for (p, a, pt), (n, b, t0, t1) in rows), sep="\n")
    print("\nDNS", *(f"  query  {QTYPES.get(t, t):4} {q}  x{n}" for (t, q), n in sorted(queries.items())),
          *(f"  answer {q} -> {a}" for q, a in sorted(answers)), sep="\n")
    print("\nTLS SNI (ClientHello)", *(f"  {a:15} {sni}" for a, sni in sorted(snis)), sep="\n")

    def flows(keep):  # peer rows where keep(ip, port); DNS/DHCP with the router is never flagged
        return [f"{p} {a} port {'-' if pt is None else pt} ({n} pkts)" for (p, a, pt), (n, *_) in rows
                if pt not in INFRA_PORTS and keep(ipaddress.ip_address(a), pt)]

    hosts = {q for _, q in queries} | {q for q, _ in answers} | {s for _, s in snis}
    print("\nFlags")
    for title, hits in (
        ("LAN UDP/TCP with heat pump (DNS/DHCP excluded)",
         flows(lambda a, pt: pt is not None and any(a in net for net in LAN_NETS))),
        ("broadcast/multicast from heat pump",  # private x.x.x.255 = broadcast on a /24 like Thomas's
         flows(lambda a, pt: a.is_multicast or a.is_private and a.packed[3] == 255)),
        ("MQTT port 1883/8883 or AWS IoT hostname", flows(lambda a, pt: pt in MQTT_PORTS)
         + sorted(h for h in hosts if ".iot." in h and h.endswith(".amazonaws.com"))),
    ):
        print(f"  [{'!' if hits else ' '}] {title}: {'; '.join(hits) or 'none'}")
    for m, lines in listed.items():
        print(f"\nPackets within ±{WINDOW} s of {m}")
        print("\n".join(lines) or "  none")


if __name__ == "__main__":
    main()
