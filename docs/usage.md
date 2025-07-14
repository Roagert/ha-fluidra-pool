# Usage

## Initial Setup

1. Install the integration through HACS or manually
2. Go to Settings -> Devices & Services
3. Click the "+ ADD INTEGRATION" button
4. Search for "Fluidra Pool"
5. Follow the configuration flow:
   - Enter your Fluidra account credentials
   - Select your pool from the list
   - Configure update intervals

## Available Entities

### Climate
- Pool temperature control
- Heat pump mode selection
- Temperature setpoint adjustment

### Sensors
- Water temperature
- pH level
- Chlorine level
- Salt level (if applicable)
- Pressure readings
- Flow rates
- Filter status
- Operating hours
- Energy consumption

### Switches
- Main pump control
- Auxiliary pumps
- Lighting control
- Heating enable/disable
- Chlorinator control
- Filter mode selection

### Binary Sensors
- Equipment status
- Fault indicators
- Filter pressure warnings
- Chemical level warnings

## Automations

You can use any of the entities in your automations. Here are some examples:

```yaml
# Turn on pool heat when temperature drops
automation:
  - alias: "Heat Pool When Cold"
    trigger:
      platform: numeric_state
      entity_id: sensor.pool_temperature
      below: 26
    action:
      service: climate.turn_on
      target:
        entity_id: climate.pool_heater

# Schedule pool pump
automation:
  - alias: "Pool Pump Schedule"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      service: switch.turn_on
      target:
        entity_id: switch.pool_pump
```

## Troubleshooting

If you encounter any issues:

1. Check your network connection
2. Verify your Fluidra account credentials
3. Ensure your pool controller is online
4. Check the Home Assistant logs for error messages
5. Refer to the [troubleshooting guide](troubleshooting.md) for more details 