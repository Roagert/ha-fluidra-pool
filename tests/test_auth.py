"""Tests for the aiohttp Cognito client. Fake credentials and tokens only."""
import asyncio
import logging

import aiohttp
import pytest
from aioresponses import CallbackResult, aioresponses
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.fluidra_pool.auth import (
    COGNITO_URL,
    FluidraAuth,
    FluidraAuthError,
    FluidraConnectionError,
    MfaRequired,
)
from custom_components.fluidra_pool.const import COGNITO_CLIENT_ID

USERNAME = "test-username"  # the account e-mail in real life
PASSWORD = "test-password-123"
ACCESS = "test-access-token-1"
ACCESS_2 = "test-access-token-2"
REFRESH = "test-refresh-token"
MFA_SESSION = "test-mfa-session"
MFA_CODE = "123456"
SECRETS = (USERNAME, PASSWORD, ACCESS, ACCESS_2, REFRESH, MFA_SESSION, MFA_CODE)

PASSWORD_AUTH = {
    "AuthFlow": "USER_PASSWORD_AUTH",
    "ClientId": COGNITO_CLIENT_ID,
    "AuthParameters": {"USERNAME": USERNAME, "PASSWORD": PASSWORD},
}
REFRESH_AUTH = {
    "AuthFlow": "REFRESH_TOKEN_AUTH",
    "ClientId": COGNITO_CLIENT_ID,
    "AuthParameters": {"REFRESH_TOKEN": REFRESH},
}
NOT_AUTHORIZED = {"status": 400, "payload": {"__type": "NotAuthorizedException"}}


def tokens(access=ACCESS, expires_in=3600, refresh=REFRESH):
    """A successful Cognito auth response."""
    result = {"AccessToken": access, "ExpiresIn": expires_in, "IdToken": "id", "TokenType": "Bearer"}
    if refresh:
        result["RefreshToken"] = refresh
    return {"payload": {"AuthenticationResult": result, "ChallengeParameters": {}}}


def mfa(challenge="SOFTWARE_TOKEN_MFA"):
    """A Cognito MFA challenge response."""
    return {"payload": {"ChallengeName": challenge, "Session": MFA_SESSION, "ChallengeParameters": {}}}


def calls(mock):
    """[(action, json body), ...] of every Cognito request, in order."""
    return [
        (c.kwargs["headers"]["X-Amz-Target"].rsplit(".", 1)[1], c.kwargs["json"])
        for c in next(iter(mock.requests.values()), [])
    ]


@pytest.fixture
def cognito():
    """Queue Cognito responses with cognito.post(COGNITO_URL, ...)."""
    with aioresponses() as mock:
        yield mock


@pytest.fixture
async def auth(hass: HomeAssistant):
    """FluidraAuth on HA's shared session."""
    return FluidraAuth(async_get_clientsession(hass), USERNAME, PASSWORD)


async def test_login_ok(auth, cognito) -> None:
    cognito.post(COGNITO_URL, **tokens())
    assert await auth.async_login() == ACCESS
    assert auth.refresh_token == REFRESH
    assert calls(cognito) == [("InitiateAuth", PASSWORD_AUTH)]
    request = next(iter(cognito.requests.values()))[0].kwargs
    assert request["headers"]["Content-Type"] == "application/x-amz-json-1.1"
    assert request["timeout"].total == 15


@pytest.mark.parametrize("challenge", ["SOFTWARE_TOKEN_MFA", "SMS_MFA"])
async def test_mfa_challenge_and_respond(auth, cognito, challenge) -> None:
    cognito.post(COGNITO_URL, **mfa(challenge))
    cognito.post(COGNITO_URL, **tokens())
    with pytest.raises(MfaRequired) as err:
        await auth.async_login()
    assert (err.value.session, err.value.challenge) == (MFA_SESSION, challenge)
    assert await auth.async_respond_mfa(err.value.session, MFA_CODE) == ACCESS
    assert calls(cognito)[1] == (
        "RespondToAuthChallenge",
        {
            "ChallengeName": challenge,
            "ClientId": COGNITO_CLIENT_ID,
            "Session": MFA_SESSION,
            "ChallengeResponses": {"USERNAME": USERNAME, f"{challenge}_CODE": MFA_CODE},
        },
    )


async def test_cached_token_reused(auth, cognito) -> None:
    cognito.post(COGNITO_URL, **tokens())
    assert [await auth.async_get_access_token() for _ in range(5)] == [ACCESS] * 5
    assert len(calls(cognito)) == 1


async def test_refresh_used_near_expiry(auth, cognito) -> None:
    cognito.post(COGNITO_URL, **tokens(expires_in=20))  # < 30 s left right away
    cognito.post(COGNITO_URL, **tokens(access=ACCESS_2, refresh=None))
    assert await auth.async_get_access_token() == ACCESS
    assert await auth.async_get_access_token() == ACCESS_2
    assert calls(cognito)[1] == ("InitiateAuth", REFRESH_AUTH)
    assert auth.refresh_token == REFRESH  # kept when Cognito does not rotate it


async def test_rejected_refresh_falls_back_to_password(hass: HomeAssistant, cognito) -> None:
    auth = FluidraAuth(async_get_clientsession(hass), USERNAME, PASSWORD, REFRESH)
    cognito.post(COGNITO_URL, **NOT_AUTHORIZED)
    cognito.post(COGNITO_URL, **tokens())
    assert await auth.async_get_access_token() == ACCESS
    assert calls(cognito) == [("InitiateAuth", REFRESH_AUTH), ("InitiateAuth", PASSWORD_AUTH)]


async def test_rejected_refresh_with_mfa_raises_auth_error(auth, cognito) -> None:
    cognito.post(COGNITO_URL, **mfa())
    cognito.post(COGNITO_URL, **tokens(expires_in=20))
    cognito.post(COGNITO_URL, **NOT_AUTHORIZED)
    with pytest.raises(MfaRequired) as err:
        await auth.async_login()
    await auth.async_respond_mfa(err.value.session, MFA_CODE)
    with pytest.raises(FluidraAuthError):
        await auth.async_get_access_token()
    assert len(calls(cognito)) == 3  # no password login after the rejected refresh


async def test_concurrent_calls_login_once(auth, cognito) -> None:
    async def slow_tokens(url, **kwargs):
        await asyncio.sleep(0.01)  # let the other callers pile up on the lock
        return CallbackResult(**tokens())

    cognito.post(COGNITO_URL, callback=slow_tokens)
    results = await asyncio.gather(*(auth.async_get_access_token() for _ in range(5)))
    assert results == [ACCESS] * 5
    assert len(calls(cognito)) == 1


@pytest.mark.parametrize("error_type", ["NotAuthorizedException", "UserNotFoundException"])
async def test_rejected_credentials_raise_auth_error(auth, cognito, error_type) -> None:
    cognito.post(COGNITO_URL, status=400, payload={"__type": error_type, "message": "nope"})
    with pytest.raises(FluidraAuthError):
        await auth.async_login()


@pytest.mark.parametrize(
    "response",
    [
        {"exception": asyncio.TimeoutError()},
        {"exception": aiohttp.ClientConnectionError()},
        {"status": 500, "body": "<html>Internal error</html>"},
        {"status": 400, "payload": {"__type": "TooManyRequestsException"}},
    ],
    ids=["timeout", "network", "http500", "throttled"],
)
async def test_transient_failures_raise_connection_error(auth, cognito, response) -> None:
    cognito.post(COGNITO_URL, **response)
    with pytest.raises(FluidraConnectionError):
        await auth.async_get_access_token()


async def test_secrets_never_logged(auth, cognito, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    cognito.post(COGNITO_URL, **mfa())
    cognito.post(COGNITO_URL, **tokens(expires_in=20))
    cognito.post(COGNITO_URL, **NOT_AUTHORIZED)
    cognito.post(COGNITO_URL, exception=asyncio.TimeoutError())
    errors = []
    try:
        await auth.async_login()
    except MfaRequired as err:
        errors.append(str(err))
    await auth.async_respond_mfa(MFA_SESSION, MFA_CODE)
    try:
        await auth.async_get_access_token()  # refresh rejected
    except FluidraAuthError as err:
        errors.append(str(err))
    try:
        await auth.async_login()
    except FluidraConnectionError as err:
        errors.append(str(err))
    assert len(errors) == 3
    assert "Refresh token rejected" in caplog.text  # something was logged
    for secret in SECRETS:
        assert secret not in caplog.text
        assert all(secret not in message for message in errors)
