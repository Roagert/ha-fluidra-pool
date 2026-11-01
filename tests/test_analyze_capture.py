"""scripts/analyze_capture.py against tiny synthetic captures (documentation IPs, no real data)."""
import importlib.util
import ipaddress
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("analyze_capture", ROOT / "scripts" / "analyze_capture.py")
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)

HP, PHONE, ROUTER, CLOUD = "192.0.2.29", "192.168.1.50", "192.0.2.1", "203.0.113.10"
HP_MAC, LAN_MAC = bytes.fromhex("020000000001"), bytes.fromhex("020000000002")
HP_ARGS = ("--hp-ip", HP, "--hp-mac", HP_MAC.hex(":"))
MDNS_MAC = bytes.fromhex("01005e0000fb")
IOT_HOST = "example-ats.iot.eu-west-1.amazonaws.com"
T0 = 1_761_998_400  # 2025-11-01 12:00:00 UTC
SECRET = b"secret-payload"


def ipv4(src, dst, proto, l4):
    a, b = ipaddress.IPv4Address(src).packed, ipaddress.IPv4Address(dst).packed
    return struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(l4), 0, 0, 64, proto, 0, a, b) + l4


def udp(src, sport, dst, dport, payload):
    return ipv4(src, dst, 17, struct.pack(">HHHH", sport, dport, 8 + len(payload), 0) + payload)


def tcp(src, sport, dst, dport, payload):
    return ipv4(src, dst, 6, struct.pack(">HHIIBBHHH", sport, dport, 0, 0, 0x50, 0x18, 65535, 0, 0) + payload)


def eth(smac, dmac, l3, etype=0x0800):
    return dmac + smac + struct.pack(">H", etype) + l3


def sll(smac, l3):
    return struct.pack(">HHH", 0, 1, 6) + smac + b"\0\0" + struct.pack(">H", 0x0800) + l3


def sll2(smac, l3):
    return struct.pack(">HHIHBB", 0x0800, 0, 1, 1, 0, 6) + smac + b"\0\0" + l3


def qname(name):
    return b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"


def dns_query(name):
    return struct.pack(">6H", 1, 0x0100, 1, 0, 0, 0) + qname(name) + struct.pack(">HH", 1, 1)


def dns_answer(name, addr):  # answer name is a compression pointer to the question
    rr = struct.pack(">HHHIH", 0xC00C, 1, 1, 60, 4) + ipaddress.IPv4Address(addr).packed
    return struct.pack(">6H", 1, 0x8180, 1, 1, 0, 0) + qname(name) + struct.pack(">HH", 1, 1) + rr


def client_hello(sni):
    n = sni.encode()
    exts = struct.pack(">HHH", 10, 2, 0)  # an extension before server_name
    exts += struct.pack(">HHHBH", 0, len(n) + 5, len(n) + 3, 0, len(n)) + n
    body = b"\x03\x03" + bytes(32) + b"\x00" + b"\x00\x02\x13\x01" + b"\x01\x00"
    body += struct.pack(">H", len(exts)) + exts
    hs = b"\x01" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x01" + struct.pack(">H", len(hs)) + hs


def pcap(frames, link=1, e="<", magic=0xA1B2C3D4):
    div = 10**6 if magic == 0xA1B2C3D4 else 10**9
    out = struct.pack(e + "IHHiIII", magic, 2, 4, 0, 0, 65535, link)
    for ts, f in frames:
        out += struct.pack(e + "4I", int(ts), round(ts % 1 * div), len(f), len(f)) + f
    return out


def _block(btype, body):
    body += b"\0" * (-len(body) % 4)
    return struct.pack("<II", btype, len(body) + 12) + body + struct.pack("<I", len(body) + 12)


def pcapng(frames, link=1):
    out = _block(0x0A0D0D0A, struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1))
    out += _block(1, struct.pack("<HHI", link, 0, 0) + struct.pack("<HHB3xHH", 9, 1, 9, 0, 0))  # ns
    for ts, f in frames:
        t = round(ts * 10**9)
        out += _block(6, struct.pack("<5I", 0, t >> 32, t & 0xFFFFFFFF, len(f), len(f)) + f)
    return out


def sample_pcap():
    """tests/fixtures/sample.pcap: DNS, AWS IoT TLS, phone<->heat-pump UDP, mDNS, ARP."""
    return pcap([
        (T0 + 0.00, eth(HP_MAC, LAN_MAC, udp(HP, 49200, ROUTER, 53, dns_query(IOT_HOST)))),
        (T0 + 0.02, eth(LAN_MAC, HP_MAC, udp(ROUTER, 53, HP, 49200, dns_answer(IOT_HOST, CLOUD)))),
        (T0 + 1.00, eth(HP_MAC, LAN_MAC, tcp(HP, 49152, CLOUD, 8883, client_hello(IOT_HOST)))),
        (T0 + 1.05, eth(LAN_MAC, HP_MAC, tcp(CLOUD, 8883, HP, 49152, b"\x16\x03\x03\x00\x00"))),
        (T0 + 30.0, eth(LAN_MAC, HP_MAC, udp(PHONE, 50000, HP, 9003, SECRET))),
        (T0 + 30.1, eth(HP_MAC, LAN_MAC, udp(HP, 9003, PHONE, 50000, b"\x01\x02"))),
        (T0 + 40.0, eth(HP_MAC, MDNS_MAC, udp(HP, 5353, "224.0.0.251", 5353, dns_query("_x._udp.local")))),
        (T0 + 50.0, eth(HP_MAC, b"\xff" * 6, bytes(28), etype=0x0806)),
    ])


def run(capsys, tmp_path, data, *args):
    path = tmp_path / "c.pcap"
    path.write_bytes(data)
    ac.main([str(path), *HP_ARGS, *args])
    return capsys.readouterr().out


@pytest.mark.parametrize("e", ["<", ">"])
@pytest.mark.parametrize("magic", [0xA1B2C3D4, 0xA1B23C4D])
def test_read_classic_pcap(e, magic):
    frame = eth(HP_MAC, LAN_MAC, udp(HP, 1, CLOUD, 2, b""))
    [(ts, link, f)] = ac.read_packets(pcap([(T0 + 0.25, frame)], e=e, magic=magic))
    assert (ts, link, f) == (T0 + 0.25, 1, frame)


def test_read_pcapng_ns_resolution():
    frame = sll2(HP_MAC, udp(HP, 1, CLOUD, 2, b""))
    [(ts, link, f)] = ac.read_packets(pcapng([(T0 + 0.25, frame)], link=276))
    assert (link, f) == (276, frame) and abs(ts - (T0 + 0.25)) < 1e-6


def test_sample_fixture(capsys):
    path = ROOT / "tests" / "fixtures" / "sample.pcap"
    assert path.read_bytes() == sample_pcap()  # committed file is exactly this synthetic capture
    ac.main([str(path), *HP_ARGS])
    out = capsys.readouterr().out
    assert "8 frames (1 not IPv4, 0 undecodable)" in out and ": 7 IPv4 packets" in out
    assert f"query  A    {IOT_HOST}  x1" in out and f"answer {IOT_HOST} -> {CLOUD}" in out
    assert f"{CLOUD:15} {IOT_HOST}" in out  # SNI, and the peer row is named
    assert ("[!] LAN UDP/TCP with heat pump (DNS/DHCP excluded): udp 192.168.1.50 port 9003 (2 pkts); "
            "udp 224.0.0.251 port 5353 (1 pkts)\n") in out
    assert "[!] broadcast/multicast from heat pump: udp 224.0.0.251 port 5353" in out
    assert f"[!] MQTT port 1883/8883 or AWS IoT hostname: tcp {CLOUD} port 8883 (2 pkts); {IOT_HOST}" in out


@pytest.mark.parametrize("args", [[], ["--hp-ip", HP], ["--hp-mac", HP_MAC.hex(":")]])
def test_hp_ip_and_mac_required(tmp_path, args):
    """No built-in default: they would be one owner's LAN address and MAC."""
    path = tmp_path / "c.pcap"
    path.write_bytes(sample_pcap())
    with pytest.raises(SystemExit):
        ac.main([str(path), *args])


def test_wan_only_sll_no_flags(capsys, tmp_path):
    out = run(capsys, tmp_path, pcap([
        (T0, sll(HP_MAC, udp(HP, 49200, ROUTER, 53, dns_query("api.example.com")))),
        (T0 + 0.1, sll(LAN_MAC, udp(ROUTER, 53, HP, 49200, dns_answer("api.example.com", CLOUD)))),
        (T0 + 1, sll(HP_MAC, tcp(HP, 49152, CLOUD, 443, client_hello("api.example.com")))),
    ], link=113))
    assert f"{CLOUD:15} api.example.com" in out
    assert "[ ] LAN UDP/TCP with heat pump (DNS/DHCP excluded): none" in out
    assert "[ ] broadcast/multicast from heat pump: none" in out
    assert "[ ] MQTT port 1883/8883 or AWS IoT hostname: none" in out


def test_lan_flow_pcapng_sll2(capsys, tmp_path):
    out = run(capsys, tmp_path, pcapng([(T0, sll2(LAN_MAC, udp(PHONE, 50000, HP, 9003, SECRET)))], link=276))
    assert "[!] LAN UDP/TCP with heat pump (DNS/DHCP excluded): udp 192.168.1.50 port 9003 (1 pkts)" in out


def test_marks_and_payload_redaction(capsys, tmp_path):
    mark = ac.clock(T0 + 31)  # local clock, so the test is timezone-independent
    out = run(capsys, tmp_path, sample_pcap(), "--marks", mark)
    assert f"Packets within ±5 s of {mark}" in out
    assert f"in  udp  {PHONE}:50000 -> {HP}:9003  42 B" in out
    assert "8883" not in out.split("Packets within")[1]  # t0+1 is outside the window
    assert SECRET.hex() not in out and "secret" not in out
    assert SECRET.hex() in run(capsys, tmp_path, sample_pcap(), "--marks", mark, "--payload")
