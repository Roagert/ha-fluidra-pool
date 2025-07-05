"""Authentication for Fluidra Pool API."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import boto3
from pycognito import AWSSRP
from botocore.exceptions import ClientError

from .const import COGNITO_REGION, COGNITO_POOL_ID, COGNITO_CLIENT_ID

_LOGGER = logging.getLogger(__name__)

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
                _LOGGER.info("Successfully authenticated with Fluidra Pool API")
                return True
            else:
                _LOGGER.error("Authentication failed")
                return False
                
        except Exception as err:
            _LOGGER.error("Authentication error: %s", err)
            return False
    
    def _authenticate_sync(self) -> Optional[Dict[str, Any]]:
        """Synchronously perform AWS Cognito authentication."""
        try:
            client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
            
            # Start SRP authentication
            aws_srp = AWSSRP(
                username=self.username,
                password=self.password,
                pool_id=COGNITO_POOL_ID,
                client_id=COGNITO_CLIENT_ID,
                client=client
            )
            auth_params = aws_srp.get_auth_params()
            
            # Initiate authentication
            response = client.initiate_auth(
                ClientId=COGNITO_CLIENT_ID,
                AuthFlow='USER_SRP_AUTH',
                AuthParameters=auth_params
            )
            
            if response.get('ChallengeName') == 'PASSWORD_VERIFIER':
                _LOGGER.debug("Processing password challenge")
                challenge_responses = aws_srp.process_challenge(
                    response['ChallengeParameters'],
                    auth_params
                )
                
                # Respond to password challenge
                response = client.respond_to_auth_challenge(
                    ClientId=COGNITO_CLIENT_ID,
                    ChallengeName='PASSWORD_VERIFIER',
                    ChallengeResponses=challenge_responses
                )
            
            # Extract tokens
            auth_result = response['AuthenticationResult']
            return {
                "access_token": auth_result['AccessToken'],
                "expiry": datetime.now() + timedelta(seconds=auth_result['ExpiresIn']),
                "id_token": auth_result['IdToken'],
                "refresh_token": auth_result['RefreshToken']
            }
            
        except ClientError as e:
            _LOGGER.error("AWS Cognito authentication failed: %s", e)
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
            "Content-Type": "application/json"
        }
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return (
            self.id_token is not None and 
            self.token_expiry is not None and 
            datetime.now() < self.token_expiry
        ) 