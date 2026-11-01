"""Constants for the Fluidra Pool integration."""
from datetime import timedelta

# Domain
DOMAIN = "fluidra_pool"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_REFRESH_TOKEN = "refresh_token"

# API Configuration
API_BASE_URL = "https://api.fluidra-emea.com"
API_DEVICES_URL = f"{API_BASE_URL}/generic/devices"

# New API Endpoints - Updated with correct working endpoints
API_ENDPOINT_DEVICE_COMPONENTS = f"{API_BASE_URL}/generic/devices/{{device_id}}/components?deviceType=connected"
API_ENDPOINT_DEVICE_UICONFIG = f"{API_BASE_URL}/generic/devices/{{device_id}}/uiconfig?appId=iaq&deviceType=connected"
API_ENDPOINT_SET_COMPONENT_VALUE = f"{API_BASE_URL}/generic/devices/{{device_id}}/components/{{component_id}}?deviceType=connected"

# AWS Cognito Configuration (based on the example)
COGNITO_REGION = "eu-west-1"
COGNITO_CLIENT_ID = "g3njunelkcbtefosqm9bdhhq1"  # Verified from token

# Update intervals
QUICK_UPDATE_INTERVAL = timedelta(seconds=1)  # 1 second after control commands (immediate feedback)

# WebSocket configuration
WS_URL = "wss://ws.fluidra-emea.com"
