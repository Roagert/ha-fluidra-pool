# Fluidra Pool Integration for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

_Integration to integrate with [Fluidra Pool][fluidra_pool]._

**This integration will set up the following platforms.**

Platform | Description
-- | --
`climate` | Control your pool temperature and heat pump.
`sensor` | Monitor pool temperature, pH, chlorine levels, and more.
`switch` | Control pool equipment like pumps and lights.
`binary_sensor` | Monitor pool equipment status.

## Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `fluidra_pool`.
4. Download _all_ the files from the `custom_components/fluidra_pool/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Fluidra Pool"

## Configuration is done in the UI

<!---->

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

## Credits

This project was generated from [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom Component Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component) template.

Code template was mainly taken from [@Ludeeus](https://github.com/ludeeus)'s [integration_blueprint][integration_blueprint] template

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[buymecoffee]: https://www.buymeacoffee.com/your-username
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg
[commits-shield]: https://img.shields.io/github/commit-activity/y/your-username/ha-fluidra-pool.svg
[commits]: https://github.com/your-username/ha-fluidra-pool/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/your-username/ha-fluidra-pool.svg
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40your--username-blue.svg
[releases-shield]: https://img.shields.io/github/release/your-username/ha-fluidra-pool.svg
[releases]: https://github.com/your-username/ha-fluidra-pool/releases
[user_profile]: https://github.com/your-username 