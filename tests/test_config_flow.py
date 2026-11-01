"""Config flow (login, MFA, reauth) and config entry data (migration, refresh token)."""
import json
import logging
from pathlib import Path
from unittest.mock import patch

import aiohttp
from aioresponses import aioresponses
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from yarl import URL

from custom_components.fluidra_pool.auth import COGNITO_URL
from custom_components.fluidra_pool.const import DOMAIN

from .conftest import COGNITO_OK

COMPONENT = Path(__file__).parents[1] / "custom_components" / DOMAIN
STRINGS = json.loads((COMPONENT / "strings.json").read_text())
LOGIN = {"username": "test-user", "password": "test-password"}
MFA_CHALLENGE = {"ChallengeName": "SOFTWARE_TOKEN_MFA", "Session": "test-mfa-session"}


@pytest.fixture
def mock_setup_entry():
    """Keep the created or reloaded entry from going online."""
    with patch("custom_components.fluidra_pool.async_setup_entry", return_value=True) as mock:
        yield mock


def translated(result: FlowResult) -> FlowResult:
    """Fail when HA would show a raw key: the flow uses only keys that strings.json has."""
    config = STRINGS["config"]
    if result["type"] is FlowResultType.FORM:
        fields = {str(key) for key in result["data_schema"].schema}
        assert config["step"][result["step_id"]]["data"].keys() == fields
        assert set((result["errors"] or {}).values()) <= config["error"].keys()
    elif result["type"] is FlowResultType.ABORT:
        assert result["reason"] in config["abort"]
    return result


async def start_user_flow(hass: HomeAssistant) -> FlowResult:
    """Open the add-integration dialog."""
    return translated(
        await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    )


async def configure(hass: HomeAssistant, result: FlowResult, **user_input) -> FlowResult:
    """Submit the form shown in result."""
    return translated(await hass.config_entries.flow.async_configure(result["flow_id"], user_input))


def cognito_calls(mock: aioresponses) -> list[dict]:
    """The JSON body of every Cognito request, in order."""
    return [call.kwargs["json"] for call in mock.requests.get(("POST", URL(COGNITO_URL)), [])]


def test_en_json_is_strings_json() -> None:
    """A custom integration ships translations/en.json; strings.json is its source."""
    assert json.loads((COMPONENT / "translations" / "en.json").read_text()) == STRINGS


async def test_user_creates_entry(hass: HomeAssistant, mock_setup_entry) -> None:
    result = await start_user_flow(hass)
    assert result["step_id"] == "user"
    with aioresponses() as mock:
        mock.post(COGNITO_URL, payload=COGNITO_OK)
        result = await configure(hass, result, **LOGIN)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fluidra Pool (test-user)"
    assert result["data"] == {**LOGIN, "refresh_token": "test-refresh-token"}
    entry = result["result"]
    assert (entry.unique_id, entry.version) == ("fluidra_pool_test-user", 2)  # same as v1 ids
    assert len(mock_setup_entry.mock_calls) == 1


async def test_mfa_code_creates_entry(hass: HomeAssistant, mock_setup_entry) -> None:
    result = await start_user_flow(hass)
    with aioresponses() as mock:
        mock.post(COGNITO_URL, payload=MFA_CHALLENGE)
        mock.post(COGNITO_URL, status=400, payload={"__type": "CodeMismatchException"})
        mock.post(COGNITO_URL, payload=COGNITO_OK)
        result = await configure(hass, result, **LOGIN)
        assert result["step_id"] == "mfa"
        result = await configure(hass, result, code="000000")
        assert (result["step_id"], result["errors"]) == ("mfa", {"base": "invalid_mfa"})
        result = await configure(hass, result, code=" 123456 ")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**LOGIN, "refresh_token": "test-refresh-token"}
    answer = cognito_calls(mock)[-1]
    assert answer["Session"] == "test-mfa-session"
    assert answer["ChallengeResponses"]["SOFTWARE_TOKEN_MFA_CODE"] == "123456"


@pytest.mark.parametrize(
    ("cognito", "error"),
    [
        ({"status": 400, "payload": {"__type": "NotAuthorizedException"}}, "invalid_auth"),
        ({"exception": aiohttp.ClientConnectionError()}, "cannot_connect"),
        ({"exception": RuntimeError()}, "unknown"),
    ],
)
async def test_login_error_shown_then_retry(
    hass: HomeAssistant, mock_setup_entry, cognito: dict, error: str
) -> None:
    result = await start_user_flow(hass)
    with aioresponses() as mock:
        mock.post(COGNITO_URL, **cognito)
        mock.post(COGNITO_URL, payload=COGNITO_OK)
        result = await configure(hass, result, **LOGIN)
        assert (result["step_id"], result["errors"]) == ("user", {"base": error})
        result = await configure(hass, result, **LOGIN)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_account_aborts(hass: HomeAssistant, config_entry) -> None:
    result = await start_user_flow(hass)
    with aioresponses() as mock:
        result = await configure(hass, result, username="test-user", password="other-password")
    assert (result["type"], result["reason"]) == (FlowResultType.ABORT, "already_configured")
    assert not cognito_calls(mock)  # aborted before logging in


@pytest.mark.parametrize("mfa", [False, True], ids=["password", "password+mfa"])
async def test_reauth_updates_login_and_reloads(
    hass: HomeAssistant, config_entry, mock_setup_entry, mfa: bool
) -> None:
    result = translated(await config_entry.start_reauth_flow(hass))
    assert result["step_id"] == "reauth_confirm"
    with aioresponses() as mock:
        if mfa:
            mock.post(COGNITO_URL, payload=MFA_CHALLENGE)
        mock.post(COGNITO_URL, payload=COGNITO_OK)
        result = await configure(hass, result, password="new-password")
        if mfa:
            assert result["step_id"] == "mfa"
            result = await configure(hass, result, code="123456")
        await hass.async_block_till_done()

    assert (result["type"], result["reason"]) == (FlowResultType.ABORT, "reauth_successful")
    login = cognito_calls(mock)[0]["AuthParameters"]
    assert login == {"USERNAME": "test-user", "PASSWORD": "new-password"}  # the entry's account
    assert config_entry.data == {
        "username": "test-user",
        "password": "new-password",
        "refresh_token": "test-refresh-token",
    }
    assert len(mock_setup_entry.mock_calls) == 1  # reloaded


async def test_v1_entry_migrates_and_loads(hass: HomeAssistant, mock_api, mock_ws) -> None:
    """An entry created by the old code (version 1) loads without user action."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="fluidra_pool_test-user",
        data={
            **LOGIN,
            "device_id": "default_device",
            "component_id": "",
            "update_interval": 15,
            "api_rate_limit": 60,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert (entry.version, entry.unique_id) == (2, "fluidra_pool_test-user")
    assert entry.data == {**LOGIN, "refresh_token": "test-refresh-token"}  # from the login


async def test_refresh_token_used_and_kept_current(
    hass: HomeAssistant, config_entry, mock_api, mock_ws, caplog: pytest.LogCaptureFixture
) -> None:
    """Setup logs in with the stored refresh token; a new token is stored without a reload."""
    caplog.set_level(logging.DEBUG)
    data = {**config_entry.data, "refresh_token": "stored-refresh-token"}
    hass.config_entries.async_update_entry(config_entry, data=data)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    coordinator = config_entry.runtime_data

    (login,) = cognito_calls(mock_api)
    assert login["AuthParameters"] == {"REFRESH_TOKEN": "stored-refresh-token"}
    assert config_entry.data["refresh_token"] == "test-refresh-token"  # Cognito sent a new one

    coordinator.api._auth.refresh_token = "rotated-refresh-token"  # renewed later, at runtime
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert config_entry.data["refresh_token"] == "rotated-refresh-token"
    assert config_entry.runtime_data is coordinator  # stored without reloading the entry
    assert "refresh-token" not in caplog.text
