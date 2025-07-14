<<<<<<< HEAD
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
[buymecoffee]: https://www.buymeacoffee.com/roagert
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg
[commits-shield]: https://img.shields.io/github/commit-activity/y/Roagert/ha-fluidra-pool.svg
[commits]: https://github.com/Roagert/ha-fluidra-pool/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/Roagert/ha-fluidra-pool.svg
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40roagert-blue.svg
[releases-shield]: https://img.shields.io/github/release/Roagert/ha-fluidra-pool.svg
[releases]: https://github.com/Roagert/ha-fluidra-pool/releases
[user_profile]: https://github.com/roagert 
=======
# Fluidra Pool Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
[![maintainer](https://img.shields.io/badge/maintainer-%40your--username-blue.svg)](https://github.com/your-username)
[![Community Forum](https://img.shields.io/badge/community-forum-brightgreen.svg)](https://community.home-assistant.io/)

A comprehensive Home Assistant integration for Fluidra Pool heat pumps, providing complete monitoring and control capabilities.

## 🏊 Features

### 🌡️ **Heat Pump Control**
- **7 Specific Modes**: Smart Heating/Cooling, Boost Heating, Silence Heating, Boost Cooling, Smart Cooling, Silence Cooling, Off
- **Temperature Control**: 10-40°C range with 0.5°C precision
- **Quick Updates**: 5-second refresh after control commands
- **Numeric API Integration**: Proper 0-6 mapping for Fluidra API

### 📊 **Comprehensive Monitoring**
- **105 Total Sensors**: Covering all aspects of pool heat pump operation
- **16 Binary Sensors**: Device status, pool conditions, user account information
- **6 Control Switches**: Pool equipment control (filtration pump, heater, chlorinator, etc.)
- **Real-time Data**: Live temperature, water quality, device status monitoring

### 🔧 **Advanced Features**
- **Entity Organization**: Logical grouping with diagnostic, monitoring, and config categories
- **API Management**: Configurable update intervals and rate limiting
- **Error Monitoring**: Comprehensive error code mapping and alarm detection
- **Multi-device Support**: Handle multiple pool devices
- **Professional Branding**: Custom icons and translations

### 📱 **Device Information**
- Device name, model, firmware, serial number
- Connection status and session management
- Component information and capabilities
- Pool specifications and water quality data

## 🚀 Installation

### Method 1: HACS (Recommended)
1. Install [HACS](https://hacs.xyz/) if you haven't already
2. Add this repository to HACS
3. Search for "Fluidra Pool" in the integrations
4. Click "Download"
5. Restart Home Assistant

### Method 2: Manual Installation
1. Download the `fluidra_pool` folder
2. Copy it to your `config/custom_components/` directory
3. Restart Home Assistant

## ⚙️ Configuration

### 1. Add Integration
1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Fluidra Pool**
4. Enter your Fluidra credentials:
   - **Username**: Your Fluidra account email
   - **Password**: Your Fluidra account password

### 2. Configure Settings (Optional)
1. Find **Fluidra Pool** in your integrations
2. Click **Configure**
3. Adjust settings:
   - **Update Interval**: 5-120 minutes (default: 30)
   - **API Rate Limit**: 10-120 requests/minute (default: 60)

## 🎛️ Usage

### Heat Pump Mode Control
1. **Open Climate Entity**: Go to your Fluidra Pool climate entity
2. **Select Preset**: Choose from 7 available modes:
   - **Smart Heating / Cooling (0)**: Automatic temperature control
   - **Boost Heating (1)**: Maximum heating power
   - **Silence Heating (2)**: Quiet heating operation
   - **Boost Cooling (3)**: Maximum cooling power
   - **Smart Cooling (4)**: Automatic cooling control
   - **Silence Cooling (5)**: Quiet cooling operation
   - **Off (6)**: Heat pump disabled
3. **Mode Applied**: Heat pump switches to selected mode
4. **Quick Update**: Status updates within 5 seconds

### Temperature Control
- **Range**: 10-40°C with 0.5°C precision
- **Units**: Celsius (configurable for Fahrenheit)
- **Quick Updates**: Immediate feedback after changes

### Entity Organization
- **Diagnostic**: Technical information and troubleshooting data
- **Monitoring**: Real-time status and measurements
- **Config**: Control settings and configuration options

## 📊 Available Sensors

### 🔥 Basic Sensors (6)
- Serial Number, Owner, Last Update
- Current Temperature, Target Temperature, Heat Pump Mode

### 📱 Device Information (12)
- Device Name, Type, Status, Model, Version, Firmware
- SKU, Thing Type, First Connection, Connection Status
- Session ID, Connectivity Timestamp

### ⚠️ Error & Alarm (4)
- Error Code, Error Message, Alarm Status, Alarm Count

### 🏊 Pool Information (3)
- Pool ID, Water Flow Status, Filtration Pump Status

### 👤 User Information (13)
- User ID, Email, Name, Phone, Address, Timezone
- Language, Account Type, Subscription Status
- Account Created, Last Login, Notifications Enabled

### 🌡️ Pool Status (16)
- Water Temperature, Air Temperature, Humidity
- pH Level, Chlorine Level, Alkalinity, Water Hardness
- Cyanuric Acid, Water Flow Rate, Pump Status
- Filter Status, Heater Status, Chlorinator Status
- Pool Light Status, Cleaning Status, Maintenance Status

### 🔧 Component Information (13)
- Component ID, Type, Name, Status, Version, Firmware
- Serial Number, Manufacturer, Model, Capabilities
- Settings, Last Update, Errors

### 🎨 UI Configuration (11)
- UI Config Version, Features, Controls, Display Options
- Language, Theme, Notifications, Automation Rules
- Schedule Settings, Maintenance Reminders, Energy Settings

### 🔍 Binary Sensors (16)
- **Device Status (5)**: Online, Error, Alarm, Maintenance Required, Updating
- **Pool/Water System (9)**: Water Flow, Pump Running, Heater Active, Chlorinator Active, Light On, Cleaning, Cover Closed, Low/High Water Level
- **User/Account (2)**: Notifications Enabled, Subscription Active

### 🎛️ Control Switches (6)
- **Pool Control**: Filtration Pump, Heater, Chlorinator, Pool Light, Cleaning, Cover

## 🔧 Troubleshooting

### Common Issues

#### Authentication Failed
- Verify your Fluidra credentials
- Check if your account is active
- Ensure you have access to the Fluidra Pool app

#### No Data Available
- Check your internet connection
- Verify the integration is properly configured
- Check the logs for API errors

#### Heat Pump Mode Not Changing
- Ensure the heat pump is online
- Check for any error codes
- Verify the component ID is correct

### Error Codes
- **E03**: Faulty water flowmeter or no flow
- **E01**: General system error
- **E02**: Communication error
- **E04**: Temperature sensor error
- **E05**: Pressure sensor error
- **E06**: Compressor error
- **E07**: Fan error
- **E08**: Defrost error
- **E09**: Water flow error
- **E10**: Power error

### Logs
Check the Home Assistant logs for detailed error information:
```yaml
logger:
  default: info
  logs:
    custom_components.fluidra_pool: debug
```

## 🛠️ Development

### Requirements
- Python 3.9+
- Home Assistant 2023.8+
- aiohttp >= 3.8.0
- boto3 >= 1.26.0
- pycognito >= 2023.5.0

### Local Development
1. Clone this repository
2. Copy to `config/custom_components/fluidra_pool/`
3. Restart Home Assistant
4. Check logs for any issues

### Testing
Run the test scripts to verify functionality:
```bash
python test_heatpump_modes.py
python test_integration_simple.py
```

## 📝 Changelog

### Version 1.0.0
- Initial release
- Complete heat pump control with 7 modes
- 105 sensors for comprehensive monitoring
- Entity organization with categories
- Professional branding and translations

## 🤝 Contributing

1. Fork this repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Fluidra](https://www.fluidra.com/) for their pool equipment
- [Home Assistant](https://www.home-assistant.io/) community
- All contributors and testers

## 📞 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/your-username/fluidra_pool/issues)
- **Community Forum**: [Home Assistant Community](https://community.home-assistant.io/)
- **Documentation**: [Integration Documentation](https://github.com/your-username/fluidra_pool)

---

**Note**: This integration is not officially affiliated with Fluidra. Use at your own risk and ensure compliance with Fluidra's terms of service. 
>>>>>>> b8a5c8247c85817c154edfa741acb07424ef5a8d
