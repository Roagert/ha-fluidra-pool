"""Authentication for Fluidra Pool API."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import boto3
import botocore.config
from botocore.exceptions import ClientError

from .const import COGNITO_REGION, COGNITO_POOL_ID, COGNITO_CLIENT_ID

_LOGGER = logging.getLogger(__name__)

# Configure boto3 to not use EC2 metadata service and optimize performance
BOTO_CONFIG = botocore.config.Config(
    connect_timeout=5,
    read_timeout=5,
    retries={'max_attempts': 2}
)

class FluidraAuth:
    """Handle Fluidra Pool authentication using AWS Cognito."""
    
    def __init__(self, username: str, password: str):
        """Initialize the authentication handler."""
        self.username = username
        self.password = password
        self.access_token: Optional[str] = None
        self.id_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        
        # Initialize Cognito client with configuration
        self.cognito_client = boto3.client(
            'cognito-idp',
            region_name=COGNITO_REGION,
            config=BOTO_CONFIG
        )
        
    async def authenticate(self) -> bool:
        """Authenticate with Fluidra Pool API."""
        try:
            # Run authentication in executor to avoid blocking
            auth_result = await asyncio.get_event_loop().run_in_executor(
                None, self._authenticate_sync
            )
            
            if auth_result:
                self.access_token = auth_result["access_token"]
                self.id_token = auth_result["id_token"]
                self.refresh_token = auth_result["refresh_token"]
                self.token_expiry = auth_result["expiry"]
                _LOGGER.debug("Successfully authenticated with Fluidra Pool API")
                _LOGGER.debug("Access token: %s...%s", 
                            self.access_token[:10] if self.access_token else 'None',
                            self.access_token[-10:] if self.access_token else 'None')
                return True
            else:
                _LOGGER.error("Authentication failed - no auth result returned")
                return False
                
        except asyncio.CancelledError:
            _LOGGER.error("Authentication was cancelled")
            return False
        except Exception as err:
            _LOGGER.error("Authentication error: %s", str(err))
            return False
    
    def _authenticate_sync(self) -> Optional[Dict[str, Any]]:
        """Synchronously perform AWS Cognito authentication."""
        try:
            _LOGGER.debug("Starting authentication process for user: %s", self.username)
            
            # Initiate direct password authentication
            try:
                _LOGGER.debug("Initiating password authentication")
                response = self.cognito_client.initiate_auth(
                    AuthFlow='USER_PASSWORD_AUTH',
                    AuthParameters={
                        'USERNAME': self.username,
                        'PASSWORD': self.password
                    },
                    ClientId=COGNITO_CLIENT_ID
                )
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code == 'NotAuthorizedException':
                    _LOGGER.error("Invalid username or password")
                elif error_code == 'UserNotFoundException':
                    _LOGGER.error("User not found")
                elif error_code == 'UserNotConfirmedException':
                    _LOGGER.error("User is not confirmed")
                else:
                    _LOGGER.error("AWS authentication error: %s - %s", 
                                error_code, 
                                e.response.get('Error', {}).get('Message', str(e)))
                return None
            
            # Extract tokens from response
            if 'AuthenticationResult' not in response:
                _LOGGER.error("No authentication result in response")
                _LOGGER.debug("Response: %s", response)
                return None
                
            auth_result = response['AuthenticationResult']
            _LOGGER.debug("Auth result keys: %s", auth_result.keys())
            
            # Check for required tokens
            if not all(key in auth_result for key in ['AccessToken', 'IdToken', 'RefreshToken']):
                _LOGGER.error("Missing required tokens in authentication result")
                _LOGGER.debug("Available tokens: %s", list(auth_result.keys()))
                return None
            
            expires_in = auth_result.get('ExpiresIn', 3600)  # Default 1 hour if not specified
            
            result = {
                "access_token": auth_result['AccessToken'],
                "expiry": datetime.now() + timedelta(seconds=expires_in),
                "id_token": auth_result['IdToken'],
                "refresh_token": auth_result['RefreshToken']
            }
            
            _LOGGER.debug("Authentication successful, tokens received")
            _LOGGER.debug("Access token: %s...%s", 
                         result["access_token"][:10],
                         result["access_token"][-10:])
            
            return result
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            _LOGGER.error("AWS Cognito error: %s - %s", 
                         error_code,
                         e.response.get('Error', {}).get('Message', str(e)))
            return None
        except Exception as e:
            _LOGGER.error("Unexpected authentication error: %s", str(e))
            return None
    
    async def refresh_token_if_needed(self) -> bool:
        """Refresh token if it's expired or about to expire."""
        if not self.token_expiry:
            _LOGGER.debug("No token expiry set, performing full authentication")
            return await self.authenticate()
        
        # Check if token expires within threshold
        if datetime.now() + timedelta(minutes=10) >= self.token_expiry:
            _LOGGER.debug("Token expires soon, refreshing...")
            return await self.authenticate()
        
        _LOGGER.debug("Token is still valid")
        return True
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if not self.access_token or not self.id_token:
            _LOGGER.warning("No access token or ID token available for headers")
            _LOGGER.debug("Access token: %s, ID token: %s", 
                         bool(self.access_token), 
                         bool(self.id_token))
            return {}
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.id_token,
            "x-access-token": self.access_token,
            "User-Agent": "Fluidra/1.0"
        }
        
        _LOGGER.debug("Generated headers with tokens")
        return headers
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        is_auth = (
            self.id_token is not None and 
            self.access_token is not None and
            self.token_expiry is not None and 
            datetime.now() < self.token_expiry
        )
        _LOGGER.debug("Authentication status: %s", "authenticated" if is_auth else "not authenticated")
        return is_auth 