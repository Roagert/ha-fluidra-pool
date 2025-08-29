"""Standalone test script for Fluidra Pool authentication and data fetching."""
import asyncio
import logging
import os
import socket
import sys
from datetime import datetime
from typing import Dict, Any

# Add the parent directory to Python path so we can import custom_components
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import aiohttp
from custom_components.fluidra_pool.auth import FluidraAuth
from custom_components.fluidra_pool.const import (
    API_CONSUMER_URL,
    API_DEVICES_URL,
    API_ENDPOINT_USER_PROFILE,
    API_ENDPOINT_USER_POOLS,
    COGNITO_CLIENT_ID,
    COGNITO_POOL_ID,
    COGNITO_REGION
)

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'fluidra_auth_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
_LOGGER = logging.getLogger(__name__)

async def _test_endpoint(session, url: str, headers: dict, endpoint_name: str):
    """Test an API endpoint and log the full response."""
    try:
        _LOGGER.info("Resolving DNS for api.fluidra-emea.com...")
        loop = asyncio.get_event_loop()
        ip = await loop.run_in_executor(None, socket.gethostbyname, "api.fluidra-emea.com")
        _LOGGER.info("Successfully resolved api.fluidra-emea.com to %s", ip)
        
        _LOGGER.info(f"Testing endpoint: {url}")
        async with session.get(url, headers=headers) as response:
            _LOGGER.info(f"Response status: {response.status}")
            
            if response.status == 200:
                try:
                    data = await response.json()
                    _LOGGER.info(f"Request successful!")
                    _LOGGER.info(f"{endpoint_name} response data: %s", data)
                    _LOGGER.info(f"{endpoint_name} test successful!")
                    return data
                except Exception as json_err:
                    _LOGGER.error(f"Failed to parse JSON response: {json_err}")
                    response_text = await response.text()
                    _LOGGER.error(f"Raw response: {response_text}")
                    return None
            else:
                response_text = await response.text()
                _LOGGER.error(f"{endpoint_name} error ({response.status}): {response_text}")
                return None
                
    except Exception as err:
        _LOGGER.error(f"Error testing {endpoint_name} endpoint: {err}")
        return None

async def test_authentication(username: str, password: str) -> bool:
    """Test authentication with Fluidra API."""
    try:
        async with aiohttp.ClientSession() as session:
            auth = FluidraAuth(
                username=username,
                password=password,
                session=session
            )
            
            # Test initial authentication
            _LOGGER.info("Testing initial authentication...")
            success = await auth.authenticate()
            if not success:
                _LOGGER.error("Initial authentication failed")
                return False
            _LOGGER.info("Initial authentication successful!")
            
            # Test token refresh
            _LOGGER.info("Testing token refresh...")
            success = await auth.refresh_token_if_needed()
            if not success:
                _LOGGER.error("Token refresh failed")
                return False
            _LOGGER.info("Token refresh successful!")
            
            # Test API endpoints
            headers = auth.get_auth_headers()
            _LOGGER.debug("Using headers: %s", {k: '****' if k in ['Authorization', 'x-api-key', 'x-access-token'] else v for k, v in headers.items()})
            
            # Test consumer data
            _LOGGER.info("\nTesting Consumer data...")
            await _test_endpoint(session, API_CONSUMER_URL, headers, "Consumer data")
            
            # Test devices data
            _LOGGER.info("\nTesting Devices data...")
            devices_data = await _test_endpoint(session, API_DEVICES_URL, headers, "Devices data")
            
            # Test additional endpoints if we have device data
            if devices_data and isinstance(devices_data, list) and len(devices_data) > 0:
                device_id = devices_data[0].get("id")
                if device_id:
                    _LOGGER.info(f"\nTesting Device Components for device: {device_id}")
                    components_url = API_ENDPOINT_DEVICE_COMPONENTS.format(device_id=device_id)
                    await _test_endpoint(session, components_url, headers, "Device Components")
                    
                    _LOGGER.info(f"\nTesting Device UI Config for device: {device_id}")
                    uiconfig_url = API_ENDPOINT_DEVICE_UICONFIG.format(device_id=device_id)
                    await _test_endpoint(session, uiconfig_url, headers, "Device UI Config")
            
            # Test user profile
            _LOGGER.info("\nTesting User Profile data...")
            await _test_endpoint(session, API_ENDPOINT_USER_PROFILE, headers, "User Profile data")
            
            # Test user pools
            _LOGGER.info("\nTesting User Pools data...")
            await _test_endpoint(session, API_ENDPOINT_USER_POOLS, headers, "User Pools data")
            
            return True
            
    except Exception as e:
        _LOGGER.exception("Error during authentication test")
        return False

async def main():
    """Main test function."""
    _LOGGER.info("Starting Fluidra authentication test")
    _LOGGER.info(f"Using Cognito configuration:")
    _LOGGER.info(f"  Region: {COGNITO_REGION}")
    _LOGGER.info(f"  Pool ID: {COGNITO_POOL_ID}")
    _LOGGER.info(f"  Client ID: {COGNITO_CLIENT_ID}")
    
    username = input("Enter your Fluidra username: ")
    password = input("Enter your Fluidra password: ")
    
    success = await test_authentication(username, password)
    
    if success:
        _LOGGER.info("All tests completed successfully!")
    else:
        _LOGGER.error("Tests failed!")

if __name__ == "__main__":
    asyncio.run(main()) 