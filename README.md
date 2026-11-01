# Fluidra Pool for Home Assistant

A custom integration for pool devices connected to the Fluidra cloud, the account you use
in the Fluidra Pool / iAquaLink+ app. It reads every device on the account over Fluidra's
REST API (every 5 minutes), gets changes pushed over Fluidra's WebSocket, and sends commands
through the cloud. Built and tested for the Amitime / Fluidra inverter pool heat pump.

Requires Home Assistant 2025.3 or newer. It uses Fluidra's EMEA cloud (`fluidra-emea.com`).
This project is not affiliated with Fluidra.

## Supported devices

| Device | Status |
|---|---|
| Amitime / Fluidra inverter heat pump (device type `amt`) | Tested: climate control and sensors. |
| Other devices that report the heat-pump components 13, 14, 15 and 19 | Get the heat-pump entities; untested. |
| Everything else (salt chlorinators, Blue Connect, …) | Set up without errors with generic entities only (error information, component count, raw component values). Proper entities need a diagnostics file from an owner: see the [issues](https://github.com/Roagert/ha-fluidra-pool/issues). |

## Installation

With [HACS](https://hacs.xyz):

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/Roagert/ha-fluidra-pool`,
   type **Integration**.
2. Search for **Fluidra Pool**, download it, restart Home Assistant.

Manually: copy `custom_components/fluidra_pool` into your `config/custom_components/`
folder and restart Home Assistant.

## Setup

1. Settings → Devices & services → **Add integration** → **Fluidra Pool**.
2. Enter the e-mail and password of your Fluidra account.
3. If the account uses two-step verification, enter the code from your authenticator app
   or SMS in the next step.

All devices on the account are added. There are no options. If Fluidra later rejects the
stored login (for example after a password change), Home Assistant asks you to log in
again with the password (and a code, if the account asks for one).

## Entities

"Heat pump" means a device that reports components 13, 14, 15 and 19.

| Entity | Type | Created for | Notes |
|---|---|---|---|
| Pool heat pump | climate | heat pumps | Off, Heat, Cool, Auto; presets Smart, Boost, Silence (Auto: Smart only); target 15–40 °C in 0.5 °C steps; action idle/heating/cooling from component 11 (unverified). |
| Power | switch | heat pumps | Turns the pump on or off in its current mode. |
| Water temperature | sensor | heat pumps | °C. |
| Air temperature | sensor | heat pumps | Outdoor air, °C. |
| Target temperature | sensor | heat pumps | Setpoint, °C. |
| Wi-Fi signal | sensor, diagnostic | heat pumps | dBm. Disabled by default. |
| No flow | binary sensor (problem) | heat pumps that report component 28 | Meaning of component 28 unverified. |
| Error information | sensor, diagnostic | every device | `ok`, or `alarm` while the cloud lists alarms for the device; attribute `alarms` holds the raw list. |
| Components | sensor, diagnostic | other devices | Number of components the cloud reports. |
| Component *N* | sensor | other devices | Raw value of each numeric component, no unit or scaling; 254, 255 and 65535 show as unavailable. Disabled by default. |

Temperatures outside −30…80 °C show as unavailable. The device page shows model, model id
(SKU), firmware and serial number. A failed command shows an error in the UI.

## Local control

Not available today: the integration is **cloud push** (Fluidra cloud REST + WebSocket).
The tested heat pump talks only to Fluidra's cloud (AWS IoT); no local API has been found
on the LAN so far. Research is in progress with an access-point packet capture
([docs/LOCAL_CAPTURE.md](docs/LOCAL_CAPTURE.md)); its outcome will be recorded in
`docs/LOCAL_DECISION.md`. If a local protocol turns up, it will be added behind the same
entities. What is known about the protocol: [PROTOCOL.md](PROTOCOL.md).

## Diagnostics and debug logs

- **Diagnostics**: Settings → Devices & services → Fluidra Pool → ⋮ → **Download
  diagnostics**. The file holds each device's info, components and UI config. Password,
  tokens, e-mail, your name, IP and MAC addresses and Wi-Fi network details are removed; the
  device id/serial and the component values stay, so please look it over before attaching it
  to an issue.
- **Debug logs**: same menu → **Enable debug logging**, reproduce the problem, then
  **Disable debug logging** to download the log.

## Upgrading from 1.x

- The config entry is migrated automatically. The options (update interval, API rate limit)
  are gone; polling is every 5 minutes with WebSocket push in between.
- Climate, water temperature and error information keep their unique ids, so their entity
  ids and history stay. Their states changed: the climate presets are now Smart / Boost /
  Silence combined with Heat / Cool / Auto, and the error sensor reads `ok` / `alarm`. Check
  automations that use them.
- Removed: the six "… Data" sensors, the chlorinator pH / ORP / salinity / free chlorine
  sensors, the climate and water temperature entities on devices that are not heat pumps, the
  **Refresh All Data** button (use `homeassistant.update_entity`) and the
  `fluidra_pool.dump_api_data` service (use Download diagnostics). Home Assistant lists the
  removed entities as "no longer provided"; delete them under Settings → Entities.

Full list of changes: [CHANGELOG.md](CHANGELOG.md).

## Development

Tests: `pip install -r requirements_test.txt && python -m pytest -q`. License: [MIT](LICENSE).
