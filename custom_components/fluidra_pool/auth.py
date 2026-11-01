"""AWS Cognito login for the Fluidra cloud (plain JSON API over aiohttp)."""
import asyncio
import logging
import time
from typing import Any

import aiohttp

from .const import COGNITO_CLIENT_ID, COGNITO_REGION

_LOGGER = logging.getLogger(__name__)

COGNITO_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"
TIMEOUT = aiohttp.ClientTimeout(total=15)
REFRESH_MARGIN = 30  # renew the access token when fewer seconds than this are left
MFA_CHALLENGES = ("SOFTWARE_TOKEN_MFA", "SMS_MFA")
# Cognito error types that mean "try again later", not "bad credentials".
RETRYABLE_ERRORS = ("TooManyRequests", "LimitExceeded", "Throttling", "InternalError")


class FluidraAuthError(Exception):
    """Credentials, MFA code or refresh token rejected: the user must act."""


class MfaRequired(FluidraAuthError):
    """Cognito asks for a second factor; answer with async_respond_mfa."""

    def __init__(self, session: str, challenge: str) -> None:
        super().__init__(challenge)
        self.session = session
        self.challenge = challenge


class FluidraConnectionError(Exception):
    """Cognito unreachable, timed out, throttled or failing (5xx): retry later."""


class FluidraAuth:
    """Cognito tokens for one Fluidra account, shared safely between tasks."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        refresh_token: str | None = None,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self.refresh_token = refresh_token
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._mfa_challenge: str | None = None
        self._lock = asyncio.Lock()

    async def async_login(self) -> str:
        """Log in with the password; return the access token or raise MfaRequired."""
        return await self._authenticate(
            "InitiateAuth",
            {
                "AuthFlow": "USER_PASSWORD_AUTH",
                "ClientId": COGNITO_CLIENT_ID,
                "AuthParameters": {"USERNAME": self._username, "PASSWORD": self._password},
            },
        )

    async def async_respond_mfa(self, session: str, code: str) -> str:
        """Answer the MfaRequired raised by async_login on this instance."""
        return await self._authenticate(
            "RespondToAuthChallenge",
            {
                "ChallengeName": self._mfa_challenge,
                "ClientId": COGNITO_CLIENT_ID,
                "Session": session,
                "ChallengeResponses": {
                    "USERNAME": self._username,
                    f"{self._mfa_challenge}_CODE": code,
                },
            },
        )

    async def async_get_access_token(self) -> str:
        """Return a valid access token, renewing it (refresh token first) when needed."""
        async with self._lock:
            if self._access_token and time.monotonic() < self._expires_at - REFRESH_MARGIN:
                return self._access_token
            if self.refresh_token:
                try:
                    return await self._authenticate(
                        "InitiateAuth",
                        {
                            "AuthFlow": "REFRESH_TOKEN_AUTH",
                            "ClientId": COGNITO_CLIENT_ID,
                            "AuthParameters": {"REFRESH_TOKEN": self.refresh_token},
                        },
                    )
                except FluidraAuthError:
                    _LOGGER.debug("Refresh token rejected")
                    self.refresh_token = None
            if self._mfa_challenge:
                # A password login would only trigger another MFA prompt.
                raise FluidraAuthError("Refresh token rejected and the account requires MFA")
            return await self.async_login()

    def invalidate_access_token(self) -> None:
        """Drop the cached access token (the API rejected it); the refresh token stays."""
        self._access_token = None

    async def _authenticate(self, action: str, payload: dict[str, Any]) -> str:
        """Run one Cognito auth call and store the tokens it returns."""
        data = await self._post(action, payload)
        if result := data.get("AuthenticationResult"):
            self._access_token = result["AccessToken"]
            self._expires_at = time.monotonic() + result["ExpiresIn"]
            self.refresh_token = result.get("RefreshToken", self.refresh_token)
            return self._access_token
        challenge = data.get("ChallengeName")
        if challenge in MFA_CHALLENGES:
            self._mfa_challenge = challenge
            raise MfaRequired(data.get("Session", ""), challenge)
        raise FluidraAuthError(f"{action}: unsupported challenge {challenge}")

    async def _post(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to the Cognito JSON API and map failures to our two exceptions."""
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": f"AWSCognitoIdentityProviderService.{action}",
        }
        try:
            async with self._session.post(
                COGNITO_URL, json=payload, headers=headers, timeout=TIMEOUT
            ) as resp:
                status = resp.status
                data = await resp.json(content_type=None) or {}
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise FluidraConnectionError(f"{action}: {type(err).__name__}") from err
        if status < 400:
            return data
        error_type = data.get("__type", "")
        if status >= 500 or any(kind in error_type for kind in RETRYABLE_ERRORS):
            raise FluidraConnectionError(f"{action}: HTTP {status} {error_type}")
        raise FluidraAuthError(f"{action}: {error_type or f'HTTP {status}'}")
