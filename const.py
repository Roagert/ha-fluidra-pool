"""Constants for the Fluidra Pool integration."""
from datetime import timedelta

# Domain
DOMAIN = "fluidra_pool"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_ID = "device_id"
CONF_COMPONENT_ID = "component_id"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_API_RATE_LIMIT = "api_rate_limit"

# API Configuration
API_BASE_URL = "https://api.fluidra-emea.com"
API_DEVICES_URL = f"{API_BASE_URL}/generic/devices"
API_CONSUMER_URL = f"{API_BASE_URL}/mobile/consumers/me"

# New API Endpoints - Updated with correct working endpoints
API_ENDPOINT_USER_PROFILE = f"{API_BASE_URL}/generic/users/me"
API_ENDPOINT_POOLS = f"{API_BASE_URL}/generic/pools"
API_ENDPOINT_POOL_STATUS = f"{API_BASE_URL}/generic/pools/{{pool_id}}/status"
API_ENDPOINT_USER_POOLS = f"{API_BASE_URL}/generic/users/me/pools"
API_ENDPOINT_DEVICE_COMPONENTS = f"{API_BASE_URL}/generic/devices/{{device_id}}/components?deviceType=connected"
API_ENDPOINT_DEVICE_UICONFIG = f"{API_BASE_URL}/generic/devices/{{device_id}}/uiconfig?appId=iaq&deviceType=connected"
API_ENDPOINT_SET_COMPONENT_VALUE = f"{API_BASE_URL}/generic/devices/{{device_id}}/components/{{component_id}}?deviceType=connected"

# AWS Cognito Configuration (based on the example)
COGNITO_REGION = "eu-west-1"
COGNITO_POOL_ID = "eu-west-1_OnopMZF9X"  # Verified from token
COGNITO_CLIENT_ID = "g3njunelkcbtefosqm9bdhhq1"  # Verified from token

# Update intervals and rate limiting
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)  # 15 minutes default (better for pool monitoring)
MIN_SCAN_INTERVAL = timedelta(minutes=2)  # Minimum 2 minutes (faster response)
MAX_SCAN_INTERVAL = timedelta(hours=2)  # Maximum 2 hours
QUICK_UPDATE_INTERVAL = timedelta(seconds=1)  # 1 second after control commands (immediate feedback)
TOKEN_REFRESH_THRESHOLD = timedelta(minutes=10)

# API Rate Limiting
DEFAULT_API_RATE_LIMIT = 60  # requests per minute
MIN_API_RATE_LIMIT = 10  # minimum requests per minute
MAX_API_RATE_LIMIT = 120  # maximum requests per minute

# Error codes for better error handling
ERROR_CODES = {
    "AUTH_FAILED": "Authentication failed",
    "RATE_LIMIT_EXCEEDED": "API rate limit exceeded",
    "DEVICE_NOT_FOUND": "Device not found",
    "POOL_NOT_FOUND": "Pool not found",
    "COMPONENT_NOT_FOUND": "Component not found",
    "API_ERROR": "API request failed",
    "NETWORK_ERROR": "Network connection error",
    "TIMEOUT_ERROR": "Request timeout",
    "INVALID_RESPONSE": "Invalid API response",
    "TOKEN_EXPIRED": "Authentication token expired",
    "REFRESH_FAILED": "Token refresh failed",
    "UNKNOWN_ERROR": "Unknown error occurred",
    # Device-specific error codes (from Fluidra API)
    "E001": "No water flow detected",
    "E002": "Water temperature sensor error",
    "E003": "Ambient temperature sensor error", 
    "E004": "High pressure alarm",
    "E005": "Low pressure alarm",
    "E006": "Compressor overload",
    "E007": "Fan motor error",
    "E008": "Heat exchanger error",
    "E009": "Communication error",
    "E010": "Power supply error",
    "E011": "Defrost sensor error",
    "E012": "Low water temperature",
    "E013": "High water temperature",
    "E014": "Phase sequence error",
    "E015": "Inverter communication error",
    "E016": "Water flow switch error",
    "W001": "Low ambient temperature",
    "W002": "Defrost mode active",
    "W003": "Filter cleaning required",
    "W004": "Maintenance required",
    "W005": "High water temperature warning"
}

# Critical error codes that should show device as "off"
CRITICAL_ERROR_CODES = {
    "E001",  # No water flow
    "E002",  # Water temp sensor error
    "E004",  # High pressure alarm  
    "E005",  # Low pressure alarm
    "E006",  # Compressor overload
    "E009",  # Communication error
    "E010",  # Power supply error
    "E014",  # Phase sequence error
    "E016"   # Water flow switch error
}

# Flow-related error codes
FLOW_ERROR_CODES = {
    "E001",  # No water flow detected
    "E016"   # Water flow switch error
}

# Smart Auto mode configuration
SMART_AUTO_DEADBAND = 1.0  # °C deadband to prevent rapid switching
SMART_AUTO_MODE_VALUE = 2  # Component 14 value for Smart Auto mode 