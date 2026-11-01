"""Config flow for Fluidra Pool: e-mail + password, an MFA code if the account asks, reauth."""
from collections.abc import Awaitable, Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import FluidraAuth, FluidraAuthError, FluidraConnectionError, MfaRequired
from .const import CONF_PASSWORD, CONF_REFRESH_TOKEN, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema({vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str})
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})
MFA_SCHEMA = vol.Schema({vol.Required("code"): str})


class FluidraPoolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Log in to the Fluidra cloud; store the login and its refresh token."""

    VERSION = 2

    def __init__(self) -> None:
        """Hold the login between the password and the MFA step."""
        self._username = ""
        self._password = ""
        self._auth: FluidraAuth | None = None
        self._mfa_session = ""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the account's e-mail and password."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)
        await self.async_set_unique_id(f"fluidra_pool_{user_input[CONF_USERNAME]}")
        self._abort_if_unique_id_configured()
        return await self._async_login("user", USER_SCHEMA, user_input)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The stored login was rejected: ask for the password again."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password of the entry's account (the e-mail cannot change)."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm", data_schema=REAUTH_SCHEMA)
        user_input = {**user_input, CONF_USERNAME: self._get_reauth_entry().data[CONF_USERNAME]}
        return await self._async_login("reauth_confirm", REAUTH_SCHEMA, user_input)

    async def async_step_mfa(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the code of the account's second factor."""
        if user_input is None:
            return self.async_show_form(step_id="mfa", data_schema=MFA_SCHEMA)
        code = user_input["code"].strip()
        return await self._async_try(
            "mfa", MFA_SCHEMA, "invalid_mfa", self._auth.async_respond_mfa(self._mfa_session, code)
        )

    async def _async_login(
        self, step_id: str, schema: vol.Schema, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Log in with the password entered in step_id."""
        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        session = async_get_clientsession(self.hass)
        self._auth = FluidraAuth(session, self._username, self._password)
        return await self._async_try(step_id, schema, "invalid_auth", self._auth.async_login())

    async def _async_try(
        self, step_id: str, schema: vol.Schema, auth_error: str, login: Awaitable[str]
    ) -> ConfigFlowResult:
        """Await a login call: store the entry, ask for an MFA code, or show step_id's error."""
        try:
            await login
        except MfaRequired as err:
            self._mfa_session = err.session
            return await self.async_step_mfa()
        except FluidraAuthError:
            error = auth_error
        except FluidraConnectionError:
            error = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error during the Fluidra login")
            error = "unknown"
        else:
            data = {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_REFRESH_TOKEN: self._auth.refresh_token,
            }
            if self.source == SOURCE_REAUTH:
                return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
            return self.async_create_entry(title=f"Fluidra Pool ({self._username})", data=data)
        return self.async_show_form(step_id=step_id, data_schema=schema, errors={"base": error})
