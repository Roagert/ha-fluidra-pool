"""Authentication for Fluidra Pool API."""
import asyncio
import logging
import socket
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import boto3
from botocore.exceptions import ClientError

from .const import COGNITO_REGION, COGNITO_POOL_ID, COGNITO_CLIENT_ID

_LOGGER = logging.getLogger(__name__)

class FluidraAuth:
    """Handle Fluidra Pool authentication using AWS Cognito."""
    
    def __init__(self, username: str, password: str, session=None):
        """Initialize the authentication handler."""
        self.username = username
        self.password = password
        self.session = session
        self.access_token: Optional[str] = None
        self.id_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        
    async def authenticate(self) -> bool:
        """Authenticate with Fluidra Pool API."""
        try:
            # DNS resolution check
            await self._check_dns_resolution()
            
            # Run authentication in executor to avoid blocking
            auth_result = await asyncio.get_event_loop().run_in_executor(
                None, self._authenticate_sync
            )
            
            if auth_result:
                self.access_token = auth_result["access_token"]
                self.id_token = auth_result["id_token"]
                self.refresh_token = auth_result["refresh_token"]
                self.token_expiry = auth_result["expiry"]
                _LOGGER.info("Successfully authenticated with Fluidra Pool API")
                _LOGGER.debug("Access token: %s...%s", self.access_token[:10], self.access_token[-10:])
                return True
            else:
                _LOGGER.error("Authentication failed")
                return False
                
        except Exception as err:
            _LOGGER.error("Authentication error: %s", err)
            return False
            
    async def _check_dns_resolution(self) -> None:
        """Check DNS resolution for the API endpoint."""
        try:
            _LOGGER.info("Resolving DNS for api.fluidra-emea.com...")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, socket.gethostbyname, "api.fluidra-emea.com")
            _LOGGER.info("Successfully resolved api.fluidra-emea.com to %s", result)
        except Exception as err:
            _LOGGER.warning("DNS resolution failed: %s", err)
    
    def _authenticate_sync(self) -> Optional[Dict[str, Any]]:
        """Synchronously perform AWS Cognito authentication using USER_PASSWORD_AUTH."""
        try:
            client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
            
            _LOGGER.info("Starting authentication process")
            
            # Use USER_PASSWORD_AUTH flow (same as working test)
            response = client.initiate_auth(
                ClientId=COGNITO_CLIENT_ID,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': self.username,
                    'PASSWORD': self.password
                }
            )
            
            # Extract tokens
            auth_result = response['AuthenticationResult']
            _LOGGER.info("Authentication successful")
            
            return {
                "access_token": auth_result['AccessToken'],
                "expiry": datetime.now() + timedelta(seconds=auth_result['ExpiresIn']),
                "id_token": auth_result['IdToken'],
                "refresh_token": auth_result['RefreshToken']
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            _LOGGER.error("AWS Cognito authentication failed - Code: %s, Message: %s", error_code, error_message)
            return None
        except Exception as e:
            _LOGGER.error("Unexpected authentication error: %s", e)
            return None
    
    async def refresh_token_if_needed(self) -> bool:
        """Refresh token if it's expired or about to expire."""
        if not self.token_expiry:
            return await self.authenticate()
        
        # Check if token expires within threshold
        if datetime.now() + timedelta(minutes=10) >= self.token_expiry:
            _LOGGER.debug("Token expires soon, refreshing...")
            return await self.authenticate()
        
        return True
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if not self.access_token:
            return {}
        
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.access_token,  # Add missing x-api-key header
            "x-access-token": self.access_token,  # Add missing x-access-token header
            "User-Agent": "Fluidra/1.0"
        }
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return (
            self.id_token is not None and 
            self.token_expiry is not None and 
            datetime.now() < self.token_expiry
        ) 