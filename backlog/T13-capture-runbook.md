---
id: T13
title: AP packet-capture runbook + pcap analyzer
phase: 5-local
points: 3
status: done
depends_on: [T02]
owner: agent
---
## Context
The only local research path Thomas chose. A laptop Wi-Fi capture can't see
heatpump↔cloud or phone↔heatpump unicast; capture must run on the UniFi AP
`192.168.1.55` (SSH, Dropbear; default creds were refused — Thomas must supply UniFi
"Device SSH Authentication" creds) or a Zyxel GS1920 (`192.168.1.253`) mirror port.
Heat pump `192.168.1.29` / `ac:15:18:98:15:f0`. Existing research to reuse (on the PR #7
branch `origin/feat/fluidra-local-cli`): `docs/unifi-network-capture-notes.md`,
`docs/local-solution-next-steps.md`. REA (`morluto/rea`) can also summarise a pcap
(`inspect_pcap_capture`, facets endpoints/dns/tls-sni) — optional, not required.

## Description
- `docs/LOCAL_CAPTURE.md` (≤1 page): exact steps — enable UniFi device SSH, one command
  that streams `tcpdump -i br0 -nn -s0 -U -w - 'host 192.168.1.29 or ether host ac:15:18:98:15:f0'`
  to `captures/heatpump.pcap`, the 3-minute test script (baseline 60 s idle → app open
  + refresh → setpoint +1 °C → wait 30 s → restore → app closed 60 s), and what to send back (only the analyzer output, not the pcap).
- `scripts/analyze_capture.py` (stdlib only, classic pcap + pcapng, ≤200 lines):
  prints per-peer table (IP, port, proto, packets, bytes, first/last time), DNS
  queries/answers, TLS SNI from ClientHello, and flags: any UDP/TCP between the heat
  pump and a **LAN** address; any broadcast/multicast from the heat pump; MQTT (1883/8883)
  or AWS IoT hostnames. Optional `--marks t1,t2` to show traffic ±5 s around event times.
  Output is redacted by default (no payload bytes).
- Test with a tiny synthetic pcap generated in the test.

## Acceptance criteria
- [x] `python3 scripts/analyze_capture.py tests/fixtures/sample.pcap` prints the tables; tests cover pcap + pcapng, DNS, SNI, LAN-flag.
- [x] Runbook commands are copy-paste ready; nothing in it requires installing software on the AP.
- [x] No payload bytes printed unless `--payload` is given.

## Log
- `scripts/analyze_capture.py` (199 lines, stdlib): pcap LE/BE µs/ns + pcapng (SHB/IDB/EPB, if_tsresol), Ethernet/SLL/SLL2, IPv4, DNS+mDNS, SNI; flags come from the peer table; DNS/DHCP (ports 53/67/68) are listed but never flagged, so router DNS doesn't trip the LAN flag.
- `tests/test_analyze_capture.py` (9 tests, synthetic builders); `tests/fixtures/sample.pcap` = `sample_pcap()` output (RFC 5737/private IPs), force-added because `.gitignore` has `*.pcap*`. Cross-checked with scapy; SNI also checked against a real OpenSSL 3.5 ClientHello; 7 mutations of the script each fail a test.
- `docs/LOCAL_CAPTURE.md`: commands pass `bash -n` and use only `which`/`date`/`tcpdump` on the AP; not run against the real AP (no access here). U02 is the field test.
- Full suite: 10 passed.
- Lead review: accepted; runbook is copy-paste ready. Field-tested only by U02.
