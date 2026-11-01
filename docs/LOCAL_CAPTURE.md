# Local capture runbook (heat pump `192.168.1.29`)

Goal: 3 minutes of everything the heat pump (`192.168.1.29`, `ac:15:18:98:15:f0`) sends and
receives, captured **on the UniFi AP `192.168.1.55`**. A laptop Wi-Fi capture cannot see the heat
pump's unicast traffic; the AP can. UniFi APs ship `tcpdump`, so nothing is installed on the AP.

## 1. Enable SSH on the AP (once)

UniFi Network → Settings → System → Advanced → **Device Authentication** (older versions:
Settings → System Settings → *Device SSH Authentication*; the wording and place vary by version,
so search Settings for "SSH"). Turn SSH on, set a username and a strong password, Apply, and wait
for the AP to re-provision. In Client Devices, check that the heat pump is connected to this AP
(if not, use that AP's IP below). On the laptop, from the repo root (put your username in `AP=`):

    AP=admin@192.168.1.55
    ssh $AP 'which tcpdump; date +%s'; date +%s

Expect a tcpdump path and two numbers within ~2 s of each other (AP and laptop clocks agree).
If ssh says `no matching host key type`, add `-o HostKeyAlgorithms=+ssh-rsa` after `ssh`.

## 2. Start the capture

Before you start, open the app and check the heat pump shows as **online** (a 2026-05-17
capture of 120 s on `br0` saw no cloud traffic at all, only ARP: the pump may have been offline,
or on another AP/VLAN path). Capture on `-i any` so every AP interface/VLAN is included.

Terminal 1 (leave it running; `captures/` is git-ignored):

    mkdir -p captures
    ssh $AP "tcpdump -i any -nn -s0 -U -w - 'host 192.168.1.29'" > captures/heatpump.pcap

Terminal 2: a sanity check (the file must grow past 24 bytes), then a clock that prints the
time each time you press Enter:

    ping -c 3 192.168.1.29; ls -l captures/heatpump.pcap
    while read; do date +%T; done

## 3. Test script (about 10 minutes; phone on the home Wi-Fi, not mobile data)

Press Enter in Terminal 2 at every ▶ to record that clock time.

1. Baseline: touch nothing for 60 s.
2. ▶ **Power-cycle the heat pump** (its mains switch/breaker off, wait 30 s, on). This is the
   most important step: on boot it must do DHCP, DNS and a fresh TLS handshake to its cloud,
   which reveals the cloud host, port and protocol. Wait 3 minutes for it to come back online.
3. ▶ Open the iAquaLink+ app, open the heat pump, pull to refresh.
4. ▶ Turn the pump **on** in the app (if that is safe now), wait 30 s, ▶ turn it off again.
5. ▶ Raise the setpoint by 1 °C, wait 30 s, ▶ restore it.
6. ▶ Close the app completely (swipe it away), then touch nothing for 2 minutes.
7. Press Ctrl-C in both terminals.

## 4. Analyse and send back

Put your ▶ times in `--marks` (comma-separated, any number):

    python3 scripts/analyze_capture.py captures/heatpump.pcap --hp-ip 192.168.1.29 --hp-mac ac:15:18:98:15:f0 --marks 14:01:00,14:05:00,14:05:20,14:05:50,14:06:20,14:06:50,14:07:20

Send back **only the analyzer output** (copy the terminal text), never the pcap: it can contain
tokens and personal data. The output has no payload bytes; do not add `--payload`.

## Fallback: Zyxel GS1920 port mirror

If AP SSH can't be enabled, use the switch (`https://192.168.1.253`, admin login). Find the
AP's port in the MAC table (AP MAC `0c:ea:14:2a:e2:a5`). Then go to Advanced Application →
Mirroring: activate mirroring, set *Monitor Port* to a free port, mark the AP's port *Mirrored*
with direction *Both*, and Apply (menu names vary by firmware). Wire the laptop to the monitor
port and run this in Terminal 1 instead of the ssh command (set `NIC` from `ip -br link`):

    NIC=eth0
    sudo tcpdump -i $NIC -nn -s0 -U -w - 'host 192.168.1.29 or ether host ac:15:18:98:15:f0' > captures/heatpump.pcap

Then run steps 3–4 unchanged, and switch mirroring off afterwards. Limit: this only sees what
crosses the AP's uplink (heat pump ↔ router/cloud), not phone ↔ heat pump traffic inside the AP.
