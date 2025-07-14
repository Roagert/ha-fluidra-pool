# Troubleshooting Guide

## Common Issues

### Connection Problems

**Symptom:** Integration shows as unavailable or entities are not updating.

**Solutions:**
1. Check your internet connection
2. Verify the Fluidra cloud service status
3. Ensure your pool controller is online
4. Try restarting Home Assistant
5. Check your firewall settings

### Authentication Errors

**Symptom:** Unable to log in or frequent disconnections.

**Solutions:**
1. Verify your Fluidra account credentials
2. Check if your account has been locked
3. Try logging out and back in through the Fluidra app
4. Clear browser cache if using the web interface
5. Contact Fluidra support if issues persist

### Entity State Issues

**Symptom:** Entities show incorrect values or states.

**Solutions:**
1. Verify the physical equipment is working correctly
2. Check sensor calibration in the pool controller
3. Compare values with the Fluidra app
4. Increase the update interval temporarily
5. Reset the entity through Home Assistant

### Performance Issues

**Symptom:** Slow updates or high resource usage.

**Solutions:**
1. Check Home Assistant system resources
2. Optimize update intervals
3. Remove unused entities
4. Check network latency to Fluidra servers
5. Consider using a different polling strategy

## Debug Logging

To enable debug logging:

1. Add to your `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.fluidra_pool: debug
```

2. Restart Home Assistant
3. Check the logs for detailed information

## Getting Help

If you're still experiencing issues:

1. Check the [GitHub issues](https://github.com/Roagert/ha-fluidra-pool/issues)
2. Create a new issue with:
   - Detailed description of the problem
   - Debug logs
   - Home Assistant version
   - Integration version
   - Pool controller model
3. Join our [Discord](https://discord.gg/Qa5fW2R) for community support 