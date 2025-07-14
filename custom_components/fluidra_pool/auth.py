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
                _LOGGER.debug("Successfully authenticated with Fluidra Pool API")
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
            try:
                _LOGGER.debug("Initiating SRP authentication")
                response = client.initiate_auth(
                    ClientId=COGNITO_CLIENT_ID,
                    AuthFlow='USER_SRP_AUTH',
                    AuthParameters=auth_params
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
            
            # Handle authentication challenges
            challenge_name = response.get('ChallengeName')
            if challenge_name:
                _LOGGER.debug("Received challenge: %s", challenge_name)
                
                if challenge_name == 'PASSWORD_VERIFIER':
                    _LOGGER.debug("Processing password verifier challenge")
                    challenge_responses = aws_srp.process_challenge(
                        response['ChallengeParameters'],
                        auth_params
                    )
                    
                    try:
                        response = client.respond_to_auth_challenge(
                            ClientId=COGNITO_CLIENT_ID,
                            ChallengeName='PASSWORD_VERIFIER',
                            ChallengeResponses=challenge_responses
                        )
                    except ClientError as e:
                        _LOGGER.error("Failed to respond to password challenge: %s", e)
                        return None
                        
                elif challenge_name == 'NEW_PASSWORD_REQUIRED':
                    _LOGGER.error("User must change password before logging in")
                    return None
                else:
                    _LOGGER.error("Unsupported challenge type: %s", challenge_name)
                    return None
            
            # Extract tokens
            if 'AuthenticationResult' not in response:
                _LOGGER.error("No authentication result in response")
                return None
                
            auth_result = response['AuthenticationResult']
            expires_in = auth_result.get('ExpiresIn', 3600)  # Default 1 hour if not specified
            
            return {
                "access_token": auth_result['AccessToken'],
                "expiry": datetime.now() + timedelta(seconds=expires_in),
                "id_token": auth_result['IdToken'],
                "refresh_token": auth_result['RefreshToken']
            }
            
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
        if not self.access_token:
            _LOGGER.warning("No access token available for headers")
            return {}
        
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.id_token,  # Include ID token as API key
            "x-access-token": self.access_token,  # Include access token explicitly
            "User-Agent": "Fluidra/1.0"  # Add User-Agent to identify client
        }
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        is_auth = (
            self.id_token is not None and 
            self.token_expiry is not None and 
            datetime.now() < self.token_expiry
        )
        _LOGGER.debug("Authentication status: %s", "authenticated" if is_auth else "not authenticated")
        return is_auth 