# Fluidra Cloud CLI

`fluidra_cloud.py` is a standalone, dependency-free CLI for the confirmed Fluidra EMEA cloud path for Thomas's Swim & Fun / Fluidra / Amitime heat pump.

## Target profile

- Device ID: `LG24440781`
- Device type: `amt`
- Signature: `BXWAB0603494724050`
- Cloud API: `https://api.fluidra-emea.com`
- Auth: AWS Cognito `USER_PASSWORD_AUTH`, client id `g3njunelkcbtefosqm9bdhhq1`

## Credentials

Use environment variables so credentials do not end up in shell history:

```bash
export FLUIDRA_USERNAME='you@example.com'
export FLUIDRA_PASSWORD='***'
```

The CLI caches the Cognito access/refresh tokens at:

```text
~/.cache/fluidra-cloud/token.json
```

Login once to seed the cache:

```bash
python3 scripts/fluidra_cloud.py --username "$FLUIDRA_USERNAME" --password "$FLUIDRA_PASSWORD" login
```

After that, normal commands can run without username/password. When the short-lived access token expires, the CLI uses the cached `refresh_token` to obtain a new access token and rewrites the cache.

Use `--no-cache` to force no cache reads/writes or `--access-token` to use a captured token directly.

## Read commands

```bash
python3 scripts/fluidra_cloud.py devices
python3 scripts/fluidra_cloud.py components
python3 scripts/fluidra_cloud.py uiconfig
python3 scripts/fluidra_cloud.py status
```

Decode a saved component dump without credentials/network:

```bash
python3 scripts/fluidra_cloud.py status --components-json tests/fixtures/lg24440781_components.json
python3 scripts/fluidra_cloud.py decode-file tests/fixtures/lg24440781_components.json
```

## Write commands are dry-run by default

The CLI only allows confirmed-safe writes:

- `13`: power, `0=off`, `1=on`
- `14`: mode, `0..6`
- `15`: setpoint, raw Celsius `×10`, range `70..400` from `c81/c82`

Examples that only print the request:

```bash
python3 scripts/fluidra_cloud.py set-setpoint 25
python3 scripts/fluidra_cloud.py set-mode smart-heating
python3 scripts/fluidra_cloud.py set-power on
python3 scripts/fluidra_cloud.py write-component 15 250
```

Send the write only with `--yes`:

```bash
python3 scripts/fluidra_cloud.py set-setpoint 25 --yes
python3 scripts/fluidra_cloud.py set-mode smart-heating-cooling --yes
python3 scripts/fluidra_cloud.py set-power off --yes
```

Recommended proof-of-control sequence:

1. `status` and note current `set_temperature_c`.
2. Dry-run `set-setpoint` to current value + 1 °C.
3. Run the same command with `--yes`.
4. Run `status` again and confirm `c15` changed.
5. Restore original setpoint.

Avoid using power as the first test because it is more disruptive.

## Confirmed component map

- `0`: running hours
- `1`: Wi-Fi RSSI dBm
- `2`: local IP
- `3`: serial/device ID
- `4`: firmware
- `5`: type, `amt`
- `6`: SKU/model code
- `7`: Wi-Fi module/model signature
- `11`: running/active state
- `13`: power
- `14`: selected mode
- `15`: setpoint, raw `×0.1 °C`
- `17`: status; UI hides controls when value is `7`
- `19`: pool/water temperature, raw `×0.1 °C`
- `28`: no-flow alarm, `1 = No Flow`, `0 = OK`
- `67`: air temperature, raw `×0.1 °C`
- `68`: water inlet temperature, raw `×0.1 °C`
- `69`: water outlet temperature, raw `×0.1 °C`
- `74`: supply voltage
- `80`: effective/current mode
- `81`: minimum setpoint °C
- `82`: maximum setpoint °C

Mode values:

- `0`: Smart Heating
- `1`: Smart Cooling
- `2`: Smart Heating / Cooling
- `3`: Boost Heating
- `4`: Silence Heating
- `5`: Boost Cooling
- `6`: Silence Cooling

## Safety notes

- Do not print tokens in logs or chat.
- Writes require `--yes`; no accidental PUT from read/status commands.
- Unknown components are rejected by `write-component`.
- Local solution work should start from passive capture / reverse engineering. Do not guess UDP or BLE packets.
