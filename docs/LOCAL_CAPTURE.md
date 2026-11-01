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

Terminal 1 (leave it running; `captures/` is git-ignored):

    mkdir -p captures
    ssh $AP "tcpdump -i br0 -nn -s0 -U -w - 'host 192.168.1.29 or ether host ac:15:18:98:15:f0'" > captures/heatpump.pcap

Terminal 2: a sanity check (the file must grow past 24 bytes), then a clock that prints the
time each time you press Enter:

    ping -c 3 192.168.1.29; ls -l captures/heatpump.pcap
    while read; do date +%T; done

If the file stays at 24 bytes, stop Terminal 1 and rerun it with `-i any` and the filter
`'host 192.168.1.29'` (`ether host` may be rejected on `any`).

## 3. Test script (about 3 minutes; phone on the home Wi-Fi, not mobile data)

Press Enter in Terminal 2 at every ▶ to record that clock time.

1. Baseline: touch nothing for 60 s.
2. ▶ Open the iAquaLink+ app, open the heat pump, pull to refresh.
3. ▶ Raise the setpoint by 1 °C, then wait 30 s.
4. ▶ Restore the setpoint.
5. ▶ Close the app completely (swipe it away), then touch nothing for 60 s.
6. Press Ctrl-C in both terminals.

## 4. Analyse and send back

Put your four ▶ times in `--marks`:

    python3 scripts/analyze_capture.py captures/heatpump.pcap --marks 14:01:00,14:01:20,14:01:50,14:02:00

Send back **only the analyzer output** (copy the terminal text), never the pcap: it can contain
tokens and personal data. The output has no payload bytes; do not add `--payload`. If the
"LAN UDP/TCP" flag says `none`, repeat steps 2–4 once with `-i any` as above, because traffic
between two clients on the same radio can bypass `br0`.

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
