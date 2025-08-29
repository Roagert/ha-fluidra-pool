"""Standalone test script for Fluidra Pool authentication without Home Assistant dependencies."""
import asyncio
import logging
import sys
import socket
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import aiohttp
import boto3
import botocore.config
import ssl

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'fluidra_auth_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
_LOGGER = logging.getLogger(__name__)

# Disable boto3 EC2 metadata service checks
os.environ['AWS_EC2_METADATA_DISABLED'] = 'true'

# Fluidra API Constants
COGNITO_REGION = "eu-west-1"
COGNITO_POOL_ID = "eu-west-1_OnopMZF9X"
COGNITO_CLIENT_ID = "g3njunelkcbtefosqm9bdhhq1"
API_ENDPOINT = "https://api.fluidra-emea.com"  # Updated to match const.py
API_CONSUMER_URL = f"{API_ENDPOINT}/mobile/consumers/me"  # Updated to match const.py
API_DEVICES_URL = f"{API_ENDPOINT}/generic/devices"  # Updated to match const.py

# Configure boto3 for better performance
BOTO_CONFIG = botocore.config.Config(
    connect_timeout=5,
    read_timeout=5,
    retries={'max_attempts': 2}
)

def verify_dns(host: str) -> bool:
    """Verify DNS resolution for a host."""
    try:
        _LOGGER.info(f"Resolving DNS for {host}...")
        ip = socket.gethostbyname(host)
        _LOGGER.info(f"Successfully resolved {host} to {ip}")
        return True
    except socket.gaierror as e:
        _LOGGER.error(f"Failed to resolve {host}: {e}")
        return False

class FluidraAuthTest:
    """Test class for Fluidra authentication."""
    
    def __init__(self, username: str, password: str, session: aiohttp.ClientSession):
        """Initialize the auth test."""
        self.username = username
        self.password = password
        self.session = session
        self.access_token = None
        self.id_token = None
        self.refresh_token = None
        self.token_expiry = None
        
        # Initialize Cognito client with configuration
        self.cognito_client = boto3.client(
            'cognito-idp',
            region_name=COGNITO_REGION,
            config=BOTO_CONFIG
        )
    
    async def authenticate(self) -> bool:
        """Authenticate with AWS Cognito."""
        try:
            _LOGGER.info("Starting authentication process")
            
            # Initiate auth
            auth_response = self.cognito_client.initiate_auth(
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': self.username,
                    'PASSWORD': self.password
                },
                ClientId=COGNITO_CLIENT_ID
            )
            
            if not auth_response:
                _LOGGER.error("No response received from authentication")
                return False
                
            # Extract tokens
            auth_result = auth_response.get('AuthenticationResult', {})
            self.access_token = auth_result.get('AccessToken')
            self.id_token = auth_result.get('IdToken')
            self.refresh_token = auth_result.get('RefreshToken')
            
            if not all([self.access_token, self.id_token, self.refresh_token]):
                _LOGGER.error("Missing required tokens")
                return False
            
            # Set token expiry
            expires_in = auth_result.get('ExpiresIn', 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
            
            _LOGGER.info("Authentication successful")
            _LOGGER.debug("Access token: %s...%s", 
                         self.access_token[:10] if self.access_token else 'None',
                         self.access_token[-10:] if self.access_token else 'None')
            return True
            
        except Exception as e:
            _LOGGER.exception("Authentication failed")
            return False
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if not self.access_token:
            _LOGGER.warning("No access token available for headers")
            return {}
        
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.id_token,
            "x-access-token": self.access_token,
            "User-Agent": "Fluidra/1.0"
        }

async def test_api_endpoint(session: aiohttp.ClientSession, url: str, headers: Dict[str, str]) -> bool:
    """Test an API endpoint with proper error handling."""
    try:
        # Extract hostname from URL for DNS verification
        host = url.split("://")[1].split("/")[0]
        if not verify_dns(host):
            _LOGGER.error(f"DNS resolution failed for {host}")
            return False
            
        _LOGGER.info(f"Testing endpoint: {url}")
        ssl_context = ssl.create_default_context()
        
        async with session.get(url, headers=headers, ssl=ssl_context) as response:
            _LOGGER.info(f"Response status: {response.status}")
            if response.status != 200:
                text = await response.text()
                _LOGGER.error(f"API error: {text}")
                return False
            _LOGGER.info("Request successful!")
            return True
            
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Connection error: {e}")
        return False
    except Exception as e:
        _LOGGER.exception(f"Unexpected error testing {url}")
        return False

async def main():
    """Main test function."""
    _LOGGER.info("Starting Fluidra authentication test")
    _LOGGER.info(f"Using Cognito configuration:")
    _LOGGER.info(f"  Region: {COGNITO_REGION}")
    _LOGGER.info(f"  Pool ID: {COGNITO_POOL_ID}")
    _LOGGER.info(f"  Client ID: {COGNITO_CLIENT_ID}")
    
    # Verify DNS resolution for API endpoints
    api_host = API_ENDPOINT.split("://")[1]
    if not verify_dns(api_host):
        _LOGGER.error(f"Cannot resolve API host {api_host}. Please check your internet connection and DNS settings.")
        return
    
    username = input("Enter your Fluidra username: ")
    password = input("Enter your Fluidra password: ")
    
    # Configure aiohttp session with proper SSL context
    ssl_context = ssl.create_default_context()
    conn = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=conn) as session:
        auth = FluidraAuthTest(username, password, session)
        
        # Test authentication
        if not await auth.authenticate():
            _LOGGER.error("Authentication failed")
            return
        
        # Get headers for API requests
        headers = auth.get_auth_headers()
        _LOGGER.debug("Using headers: %s", 
                     {k: '****' if k in ['Authorization', 'x-api-key', 'x-access-token'] else v 
                      for k, v in headers.items()})
        
        # Test API endpoints
        endpoints = [
            ("Consumer data", API_CONSUMER_URL),
            ("Devices data", API_DEVICES_URL)
        ]
        
        for name, url in endpoints:
            _LOGGER.info(f"\nTesting {name}...")
            if await test_api_endpoint(session, url, headers):
                _LOGGER.info(f"{name} test successful!")
            else:
                _LOGGER.error(f"{name} test failed!")

if __name__ == "__main__":
    asyncio.run(main()) 