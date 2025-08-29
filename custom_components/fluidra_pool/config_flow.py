"""Config flow for Fluidra Pool integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN, 
    CONF_USERNAME, 
    CONF_PASSWORD, 
    CONF_DEVICE_ID, 
    CONF_COMPONENT_ID,
    CONF_UPDATE_INTERVAL,
    CONF_API_RATE_LIMIT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_API_RATE_LIMIT,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_API_RATE_LIMIT,
    MAX_API_RATE_LIMIT,
)
from .auth import FluidraAuth

_LOGGER = logging.getLogger(__name__)

class FluidraPoolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fluidra Pool."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._username: Optional[str] = None
        self._password: Optional[str] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Test authentication
                auth = FluidraAuth(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                if await auth.refresh_token_if_needed():
                    self._username = user_input[CONF_USERNAME]
                    self._password = user_input[CONF_PASSWORD]
                    
                    # Create unique ID for this configuration
                    unique_id = f"fluidra_pool_{self._username}"
                    
                    # Check if this configuration already exists
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    
                    # Create the config entry directly
                    return self.async_create_entry(
                        title=f"Fluidra Pool ({self._username})",
                        data={
                            CONF_USERNAME: self._username,
                            CONF_PASSWORD: self._password,
                            CONF_DEVICE_ID: "default_device",  # Will be discovered during setup
                            CONF_COMPONENT_ID: "",  # Will be discovered during setup
                            CONF_UPDATE_INTERVAL: int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60),
                            CONF_API_RATE_LIMIT: DEFAULT_API_RATE_LIMIT,
                        },
                    )
                else:
                    errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.error("Authentication error: %s", err)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return FluidraPoolOptionsFlow(config_entry)

class FluidraPoolOptionsFlow(config_entries.OptionsFlow):
    """Handle Fluidra Pool options."""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
    
    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        config_entry = self.config_entry
        
        if user_input is not None:
            # Validate input
            update_interval = user_input[CONF_UPDATE_INTERVAL]
            api_rate_limit = user_input[CONF_API_RATE_LIMIT]
            
            # Validate update interval
            if update_interval < int(MIN_SCAN_INTERVAL.total_seconds() / 60):
                update_interval = int(MIN_SCAN_INTERVAL.total_seconds() / 60)
            elif update_interval > int(MAX_SCAN_INTERVAL.total_seconds() / 60):
                update_interval = int(MAX_SCAN_INTERVAL.total_seconds() / 60)
            
            # Validate API rate limit
            if api_rate_limit < MIN_API_RATE_LIMIT:
                api_rate_limit = MIN_API_RATE_LIMIT
            elif api_rate_limit > MAX_API_RATE_LIMIT:
                api_rate_limit = MAX_API_RATE_LIMIT
            
            # Update config entry
            new_data = config_entry.data.copy()
            new_data[CONF_UPDATE_INTERVAL] = update_interval
            new_data[CONF_API_RATE_LIMIT] = api_rate_limit
            
            self.hass.config_entries.async_update_entry(
                config_entry, data=new_data
            )
            
            return self.async_create_entry(title="", data=user_input)
        
        # Get current values
        current_update_interval = config_entry.data.get(
            CONF_UPDATE_INTERVAL, 
            int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60)
        )
        current_api_rate_limit = config_entry.data.get(
            CONF_API_RATE_LIMIT, 
            DEFAULT_API_RATE_LIMIT
        )
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=current_update_interval,
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=int(MIN_SCAN_INTERVAL.total_seconds() / 60),
                        max=int(MAX_SCAN_INTERVAL.total_seconds() / 60)
                    )
                ),
                vol.Optional(
                    CONF_API_RATE_LIMIT,
                    default=current_api_rate_limit,
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_API_RATE_LIMIT, max=MAX_API_RATE_LIMIT)
                ),
            }),
        )

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class AlreadyConfigured(HomeAssistantError):
    """Error to indicate device is already configured.""" 