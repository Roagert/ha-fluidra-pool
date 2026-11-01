# Draft replies for issues #3 #4 #5 #8 (T12)

Drafts only — not posted. Post when the release with T12 is out; replace "the next release"
with its version number.

## #3 Irripool iSalt — only generic entities

Thanks for the report, and sorry for the wait. The integration so far only knows the
Amitime heat pump, so your iSalt only got generic entities.

What the next release does for your device: it sets up without errors, and the device shows
an **Error information** sensor (ok/alarm) and a **Components** diagnostic sensor (how many
values the cloud reports). Each numeric value the cloud reports also gets a
**Component N** sensor with the raw value (no unit, no scaling), disabled by default:
enable the ones you want under the device's entities. Values 254, 255 and 65535 show as
unavailable (they look like "no data").

To map the right values to pH, salt, etc., could you install the next release and send a
diagnostics file? Settings → Devices & services → Fluidra Pool → ⋮ → Download diagnostics.
Password, tokens, e-mail and network details are removed; the device serial and the values
stay. Please have a quick look before attaching it, and note what the Fluidra app shows at
the same moment (e.g. pH, salt, temperature) — that is what lets us match the numbers.

## #4 Blue Connect Gold — uiconfig 500, water temperature 404.2 °C

Thanks for the report. The 404.2 °C came from the integration reading component 19 as a
heat-pump water temperature on every device; on your Blue Connect it means something else.

What the next release does for your device: the cloud's 500 on the UI config no longer
matters, and there is no water temperature sensor any more on devices that are not a heat
pump (and any temperature outside −30…80 °C shows as unavailable). You get an **Error
information** sensor, a **Components** diagnostic sensor, and a disabled-by-default
**Component N** sensor per numeric value with the raw number (e.g. Component 19 = 4042),
no unit or scaling.

Could you install it and send a diagnostics file? Settings → Devices & services → Fluidra
Pool → ⋮ → Download diagnostics. Password, tokens, e-mail and network details are removed;
the device serial and the values stay, so please have a quick look before attaching it. If
you can, also note the temperature, pH and ORP the Blue Connect app shows at that moment.

## #5 Tecno LC2 / Zodiac IQ 12 — "Component 13 NOT FOUND", uiconfig 500

Thanks for the report. The integration expected every device to be an Amitime heat pump
(component 13 = power), which yours is not, hence the error and the unknown sensors.

What the next release does for your device: heat-pump controls are only created for
devices that report the heat-pump components (13, 14, 15 and 19), so your device sets up
without that error, also when the cloud answers 500 for its UI config. It shows an **Error
information** sensor, a **Components** diagnostic sensor, and a disabled-by-default
**Component N** sensor per numeric value with the raw number (no unit, no scaling;
254/255/65535 show as unavailable). There is no thermostat entity for it.

Could you install it and send a diagnostics file? Settings → Devices & services → Fluidra
Pool → ⋮ → Download diagnostics. Password, tokens, e-mail and network details are removed;
the device serial and the values stay, so please have a quick look before attaching it, and
tell us what the Fluidra app shows at that moment (mode, temperatures, setpoint).

## #8 Ei2q Evo — pH 2.54, ORP mixed with setpoint, temperature/salinity 0.0

Thanks for the detailed report. Those pH/ORP/salinity sensors were guesses that did not
match your device: 2.54 is the raw value 254, which most likely means "no data".

What the next release does for your device: the guessed pH, ORP, salinity, free chlorine and
water temperature sensors are gone, so no more wrong numbers. You get an **Error
information** sensor, a **Components** diagnostic sensor, and a disabled-by-default
**Component N** sensor per numeric value with the raw number (no unit, no scaling);
254, 255 and 65535 show as unavailable.

Could you install it and send a diagnostics file? Settings → Devices & services → Fluidra
Pool → ⋮ → Download diagnostics. Password, tokens, e-mail and network details are removed;
the device serial and the values stay, so please have a quick look before attaching it.
Noting the pH, pH setpoint, ORP, ORP setpoint, salinity and temperature the Fluidra app
shows at the same moment would help a lot to tell the values apart.
