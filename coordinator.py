"""Data coordinator for Fluidra Pool integration."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

import json

from .const import (
    API_DEVICES_URL,
    API_CONSUMER_URL,
    API_ENDPOINT_USER_PROFILE,
    API_ENDPOINT_POOL_STATUS,
    API_ENDPOINT_USER_POOLS,
    API_ENDPOINT_DEVICE_COMPONENTS,
    API_ENDPOINT_DEVICE_UICONFIG,
    API_ENDPOINT_SET_COMPONENT_VALUE,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    QUICK_UPDATE_INTERVAL,
    DEFAULT_API_RATE_LIMIT,
    MIN_API_RATE_LIMIT,
    MAX_API_RATE_LIMIT,
    CONF_DEVICE_ID,
    CONF_COMPONENT_ID,
    CONF_UPDATE_INTERVAL,
    CONF_API_RATE_LIMIT,
    ERROR_CODES,
    WS_URL,
    WS_RECONNECT_DELAY,
    WS_MAX_RECONNECT_ATTEMPTS,
)
from .auth import FluidraAuth

_LOGGER = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds

class FluidraPoolDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Fluidra Pool data."""
    
    def __init__(self, hass: HomeAssistant, username: str, password: str, config_entry=None):
        """Initialize the coordinator."""
        # Get configuration from config entry
        update_interval = DEFAULT_SCAN_INTERVAL
        api_rate_limit = DEFAULT_API_RATE_LIMIT
        
        if config_entry:
            update_interval = config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_SCAN_INTERVAL)
            if isinstance(update_interval, int):
                update_interval = timedelta(minutes=update_interval)
            elif isinstance(update_interval, str):
                # Convert string to timedelta
                try:
                    minutes = int(update_interval)
                    update_interval = timedelta(minutes=minutes)
                except ValueError:
                    update_interval = DEFAULT_SCAN_INTERVAL
            
            api_rate_limit = config_entry.data.get(CONF_API_RATE_LIMIT, DEFAULT_API_RATE_LIMIT)
        
        # Ensure update interval is within bounds
        if update_interval < MIN_SCAN_INTERVAL:
            update_interval = MIN_SCAN_INTERVAL
        elif update_interval > MAX_SCAN_INTERVAL:
            update_interval = MAX_SCAN_INTERVAL
        
        # Ensure API rate limit is within bounds
        if api_rate_limit < MIN_API_RATE_LIMIT:
            api_rate_limit = MIN_API_RATE_LIMIT
        elif api_rate_limit > MAX_API_RATE_LIMIT:
            api_rate_limit = MAX_API_RATE_LIMIT
        
        super().__init__(
            hass,
            _LOGGER,
            name="Fluidra Pool",
            update_interval=update_interval,
        )
        
        self.session = aiohttp.ClientSession()
        self.auth = FluidraAuth(username, password, self.session)
        self.devices: Dict[str, Any] = {}
        self.consumer_data: Dict[str, Any] = {}
        self.user_profile_data: Dict[str, Any] = {}
        self.pool_status_data: Dict[str, Any] = {}
        self.user_pools_data: Dict[str, Any] = {}
        self.device_components_data: Dict[str, Any] = {}
        self.device_uiconfig_data: Dict[str, Any] = {}
        self.error_information: Dict[str, Any] = {}
        self.config_entry = config_entry
        
        # API rate limiting
        self.api_rate_limit = api_rate_limit
        self.api_calls = []
        self.last_api_call = None
        self.next_update = datetime.now()
        
        # Quick update management
        self.quick_update_scheduled = False
        self.quick_update_task = None

        # WebSocket real-time updates
        self._ws_task: Optional[asyncio.Task] = None
        self._ws_running = False

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        self._ws_running = False
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if self.quick_update_task and not self.quick_update_task.done():
            self.quick_update_task.cancel()
        await self.session.close()
        await super().async_shutdown()

    # ── WebSocket real-time updates ───────────────────────────────────────────

    def _start_websocket(self) -> None:
        """Start the WebSocket listener task if not already running."""
        if self._ws_task is None or self._ws_task.done():
            self._ws_running = True
            self._ws_task = self.hass.async_create_task(self._ws_listener())
            _LOGGER.info("WebSocket listener task started")

    async def _ws_listener(self) -> None:
        """Maintain a persistent WebSocket connection to the Fluidra cloud."""
        attempts = 0
        while self._ws_running and attempts < WS_MAX_RECONNECT_ATTEMPTS:
            try:
                await self.auth.authenticate()
                token = self.auth.access_token
                if not token:
                    _LOGGER.warning("WebSocket: no auth token, retrying in %ds", WS_RECONNECT_DELAY)
                    await asyncio.sleep(WS_RECONNECT_DELAY)
                    attempts += 1
                    continue

                headers = {"Authorization": f"Bearer {token}"}
                async with self.session.ws_connect(WS_URL, headers=headers, heartbeat=30) as ws:
                    _LOGGER.info("WebSocket connected to %s", WS_URL)
                    attempts = 0  # reset on successful connect

                    # Subscribe to all known devices
                    for device_id in self.devices:
                        sub_msg = json.dumps({
                            "action": "subsDevice",
                            "deviceType": "connected",
                            "deviceId": device_id,
                        })
                        await ws.send_str(sub_msg)
                        _LOGGER.debug("WebSocket subscribed to device %s", device_id)

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._ws_handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            _LOGGER.error("WebSocket error: %s", ws.exception())
                            break
                        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                            _LOGGER.info("WebSocket closed")
                            break

            except asyncio.CancelledError:
                return
            except Exception as exc:
                _LOGGER.warning("WebSocket disconnected: %s — reconnecting in %ds", exc, WS_RECONNECT_DELAY)

            if self._ws_running:
                await asyncio.sleep(WS_RECONNECT_DELAY)
                attempts += 1

        if attempts >= WS_MAX_RECONNECT_ATTEMPTS:
            _LOGGER.error("WebSocket: max reconnect attempts reached; falling back to polling")

    async def _ws_handle_message(self, raw: str) -> None:
        """Process an incoming WebSocket message and update component state."""
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            _LOGGER.debug("WebSocket: non-JSON message ignored")
            return

        device_id = event.get("deviceId") or event.get("device_id")
        component_id = event.get("componentId") or event.get("id")
        reported = event.get("reportedValue") if "reportedValue" in event else event.get("value")

        if device_id and component_id is not None and reported is not None:
            if device_id not in self.device_components_data:
                self.device_components_data[device_id] = {}
            comp_key = int(component_id) if str(component_id).isdigit() else component_id
            existing = self.device_components_data[device_id].get(comp_key, {})
            if isinstance(existing, dict):
                existing["reportedValue"] = reported
            else:
                self.device_components_data[device_id][comp_key] = {"reportedValue": reported}
            _LOGGER.debug("WebSocket update: device=%s component=%s value=%s", device_id, comp_key, reported)
            self.async_set_updated_data(self.data)
    
    def _check_rate_limit(self) -> bool:
        """Check if we can make an API call based on rate limiting."""
        now = datetime.now()
        # Remove old API calls (older than 1 minute)
        self.api_calls = [call_time for call_time in self.api_calls 
                         if now - call_time < timedelta(minutes=1)]
        # Check if we're under the rate limit
        if len(self.api_calls) >= self.api_rate_limit:
            _LOGGER.warning("API rate limit reached (%d calls per minute)", self.api_rate_limit)
            return False
        _LOGGER.debug("API rate limit check: %d/%d calls in last minute", len(self.api_calls), self.api_rate_limit)
        return True
    
    def _record_api_call(self) -> None:
        """Record an API call for rate limiting."""
        now = datetime.now()
        self.api_calls.append(now)
        self.last_api_call = now
        _LOGGER.debug("API call recorded at %s", now)
    
    async def schedule_quick_update(self) -> None:
        """Schedule a quick update after control commands."""
        # Check if a regular update is already happening soon
        if hasattr(self, '_update_task') and self._update_task and not self._update_task.done():
            _LOGGER.debug("Regular update already in progress, skipping quick update.")
            return
            
        if self.quick_update_scheduled:
            _LOGGER.debug("Quick update already scheduled, skipping.")
            return
            
        self.quick_update_scheduled = True
        if self.quick_update_task and not self.quick_update_task.done():
            self.quick_update_task.cancel()
        _LOGGER.info("Scheduling quick update in %d seconds", QUICK_UPDATE_INTERVAL.total_seconds())
        self.quick_update_task = asyncio.create_task(self._quick_update())
    
    async def _quick_update(self) -> None:
        """Perform a quick update after control commands."""
        try:
            await asyncio.sleep(QUICK_UPDATE_INTERVAL.total_seconds())
            
            # Double-check if a regular update is happening before proceeding
            if hasattr(self, '_update_task') and self._update_task and not self._update_task.done():
                _LOGGER.debug("Regular update started during quick update delay, skipping quick update.")
                return
                
            _LOGGER.info("Performing quick update after control command.")
            await self.async_request_refresh()
        except asyncio.CancelledError:
            _LOGGER.debug("Quick update task cancelled.")
        finally:
            self.quick_update_scheduled = False
    
    async def _fetch_with_retries(self, fetch_func, *args, **kwargs):
        """Helper to retry fetch functions with logging."""
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                _LOGGER.info(f"Attempt {attempt} for {fetch_func.__name__}")
                await fetch_func(*args, **kwargs)
                # Check if data is not empty (for known attributes)
                if hasattr(self, fetch_func.__name__.replace('_fetch_', '') + '_data'):
                    data = getattr(self, fetch_func.__name__.replace('_fetch_', '') + '_data')
                    if data:
                        _LOGGER.info(f"{fetch_func.__name__} succeeded on attempt {attempt}")
                        return
                    else:
                        _LOGGER.warning(f"{fetch_func.__name__} returned empty data on attempt {attempt}")
                else:
                    return
            except Exception as err:
                _LOGGER.error(f"{fetch_func.__name__} failed on attempt {attempt}: {err}")
            await asyncio.sleep(RETRY_DELAY)
        _LOGGER.error(f"{fetch_func.__name__} failed after {RETRY_ATTEMPTS} attempts.")
    
    async def async_request_refresh(self) -> None:
        _LOGGER.info("[Fluidra Debug] Coordinator async_request_refresh called at %s", datetime.now())
        await super().async_request_refresh()
        _LOGGER.info("[Fluidra Debug] Coordinator async_request_refresh finished at %s", datetime.now())

    async def _async_update_data(self) -> Dict[str, Any]:
        _LOGGER.info("[Fluidra Debug] Coordinator _async_update_data called at %s (scheduled automatic update)", datetime.now())
        _LOGGER.info("[Fluidra Debug] Update interval: %s, Last update success: %s", 
                    self.update_interval, self.last_update_success)
        
        try:
            # Ensure we're authenticated before making any API calls
            if not await self.auth.authenticate():
                raise ConfigEntryAuthFailed("Failed to authenticate with Fluidra API")

            # Track successful fetches - don't fail completely if some endpoints fail
            fetch_results = {}
            
            # Core data fetches (most important)
            try:
                await self._fetch_with_retries(self._fetch_devices_data)
                fetch_results['devices'] = True
            except Exception as e:
                _LOGGER.warning("Failed to fetch devices data: %s", e)
                fetch_results['devices'] = False
            
            # Optional data fetches (less critical)
            for fetch_name, fetch_func in [
                ('consumer', self._fetch_consumer_data),
                ('user_profile', self._fetch_user_profile_data),
                ('user_pools', self._fetch_user_pools_data)
            ]:
                try:
                    await self._fetch_with_retries(fetch_func)
                    fetch_results[fetch_name] = True
                except Exception as e:
                    _LOGGER.warning("Failed to fetch %s data: %s", fetch_name, e)
                    fetch_results[fetch_name] = False
            
            # Device-specific fetches (if we have devices)
            if self.devices:
                first_device_id = next(iter(self.devices.keys()))
                for fetch_name, fetch_func, args in [
                    ('device_components', self._fetch_device_components_data, [first_device_id]),
                    ('device_uiconfig', self._fetch_device_uiconfig_data, [first_device_id])
                ]:
                    try:
                        await self._fetch_with_retries(fetch_func, *args)
                        fetch_results[fetch_name] = True
                    except Exception as e:
                        _LOGGER.warning("Failed to fetch %s data: %s", fetch_name, e)
                        fetch_results[fetch_name] = False
            
            # Process error information after all device data is loaded
            self._process_error_information()
            
            # Return a summary dict for debugging
            data = {
                "consumer_data": self.consumer_data,
                "devices": self.devices,
                "user_profile_data": self.user_profile_data,
                "user_pools_data": self.user_pools_data,
                "device_components_data": self.device_components_data,
                "device_uiconfig_data": self.device_uiconfig_data,
                "error_information": self.error_information,
                "fetch_results": fetch_results,
            }
            
            # Consider update successful if we got at least device data
            if fetch_results.get('devices', False):
                _LOGGER.info("[Fluidra Debug] Update completed successfully (core data fetched) at %s", datetime.now())
                _LOGGER.info("[Fluidra Debug] Fetch results: %s", fetch_results)
                _LOGGER.info("[Fluidra Debug] Data fetched - devices: %s, components: %s, errors: %s",
                            len(self.devices) if self.devices else 0,
                            len(self.device_components_data) if self.device_components_data else 0,
                            len(self.error_information) if self.error_information else 0)
                # Start WebSocket listener on first successful fetch
                self._start_websocket()
                return data
            else:
                raise UpdateFailed("Failed to fetch core device data")
                
        except ConfigEntryAuthFailed as auth_err:
            _LOGGER.error("[Fluidra Debug] Authentication failed in _async_update_data: %s", auth_err)
            raise
        except Exception as err:
            _LOGGER.error("[Fluidra Debug] Error in _async_update_data: %s", err)
            raise UpdateFailed(f"Fluidra automatic update failed: {err}")
    
    async def _fetch_consumer_data(self) -> None:
        """Fetch consumer data from API."""
        try:
            # Check rate limiting
            if not self._check_rate_limit():
                _LOGGER.warning("Rate limit exceeded for consumer data request")
                return
            
            # Ensure authentication
            if not await self.auth.refresh_token_if_needed():
                _LOGGER.error("Authentication failed for consumer data request")
                return
            
            _LOGGER.debug("Fetching consumer data from %s", API_CONSUMER_URL)
            headers = self.auth.get_auth_headers()
            _LOGGER.debug("Request headers (masked): %s", {k: '****' if k in ['Authorization', 'x-api-key', 'x-access-token'] else v for k, v in headers.items()})
            
            # Record API call
            self._record_api_call()
            
            async with self.session.get(API_CONSUMER_URL, headers=headers) as response:
                _LOGGER.debug("Consumer data response status: %s", response.status)
                if response.status == 200:
                    self.consumer_data = await response.json()
                    _LOGGER.debug("Successfully fetched consumer data: %s", self.consumer_data)
                elif response.status == 401:
                    response_text = await response.text()
                    _LOGGER.error("Authentication failed for consumer data (401): %s", response_text)
                    self.consumer_data = {}
                elif response.status == 403:
                    response_text = await response.text()
                    _LOGGER.error("Access forbidden for consumer data (403): %s", response_text)
                    self.consumer_data = {}
                else:
                    response_text = await response.text()
                    _LOGGER.error("Failed to fetch consumer data (%s): %s", response.status, response_text)
                    self.consumer_data = {}
        except Exception as err:
            _LOGGER.error("Error fetching consumer data: %s", err)
            self.consumer_data = {}
    
    async def _fetch_devices_data(self) -> None:
        """Fetch devices data from API."""
        try:
            # Check rate limiting
            if not self._check_rate_limit():
                _LOGGER.warning("Rate limit exceeded for devices data request")
                return
            
            # Ensure authentication
            if not await self.auth.refresh_token_if_needed():
                _LOGGER.error("Authentication failed for devices data request")
                return
            
            _LOGGER.debug("Fetching devices data from %s", API_DEVICES_URL)
            headers = self.auth.get_auth_headers()
            
            # Record API call
            self._record_api_call()
            
            async with self.session.get(API_DEVICES_URL, headers=headers) as response:
                _LOGGER.debug("Devices data response status: %s", response.status)
                if response.status == 200:
                    raw_data = await response.json()
                    _LOGGER.debug("Raw devices data: %s", raw_data)
                    self.devices = self._process_devices_data(raw_data)
                    _LOGGER.info("Successfully fetched devices data: %d devices found", len(self.devices))
                    _LOGGER.debug("Processed devices data: %s", self.devices)
                elif response.status == 401:
                    response_text = await response.text()
                    _LOGGER.error("Authentication failed for devices data (401): %s", response_text)
                    self.devices = {}
                elif response.status == 403:
                    response_text = await response.text()
                    _LOGGER.error("Access forbidden for devices data (403): %s", response_text)
                    self.devices = {}
                else:
                    response_text = await response.text()
                    _LOGGER.error("Failed to fetch devices data (%s): %s", response.status, response_text)
                    self.devices = {}
        except Exception as err:
            _LOGGER.error("Error fetching devices data: %s", err)
            self.devices = {}
    
    def _process_devices_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and extract relevant data from devices response."""
        processed_data = {}
        
        try:
            # Handle different response formats
            if isinstance(raw_data, list):
                # If response is a list, process each item
                for device in raw_data:
                    device_id = device.get("id")
                    if device_id:
                        processed_data[device_id] = self._process_device(device)
            elif "data" in raw_data and isinstance(raw_data["data"], list):
                # If response has a data field with list
                for device in raw_data["data"]:
                    device_id = device.get("id")
                    if device_id:
                        processed_data[device_id] = self._process_device(device)
            else:
                # Try to process as single device
                device_id = raw_data.get("id")
                if device_id:
                    processed_data[device_id] = self._process_device(raw_data)
            
            _LOGGER.debug("Processed %d devices", len(processed_data))
            
        except Exception as err:
            _LOGGER.error("Error processing devices data: %s", err)
            processed_data = {}
        
        return processed_data
    
    def _process_device(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single device with all available information."""
        device_id = device.get("id")
        
        # Basic device information
        processed_device = {
            "id": device_id,
            "name": device.get("name") or device.get("info", {}).get("name", "Unknown Device"),
            "serial_number": device.get("sn") or device.get("serialNumber") or device.get("SerialNumber"),
            "type": device.get("type"),
            "status": device.get("status"),
            "components": {},
            
            # Device information from API analysis
            "device_name": device.get("info", {}).get("name"),
            "device_type": device.get("type"),
            "device_status": device.get("status"),
            "device_model": device.get("info", {}).get("family"),
            "device_version": device.get("vr"),
            "device_firmware": device.get("vr") or device.get("currentFirmwareVersion"),
            "device_sku": device.get("sku"),
            "device_thing_type": device.get("thingType"),
            "device_first_connection": device.get("firstConnection"),
            "device_connection_status": "connected" if device.get("connectivity", {}).get("connected") else "disconnected",
            "device_session_id": device.get("connectivity", {}).get("sessionIdentifier"),
            "device_connectivity_timestamp": device.get("connectivity", {}).get("timestamp"),
            
            # Pool information
            "pool_id": device.get("poolId"),
            
            # Error and alarm information
            "alarms": device.get("alarms", []),
            "error_code": None,
            "error_message": None,
            "alarm_status": "normal",
            "alarm_count": 0,
        }
        
        # Process alarms and errors with enhanced detail
        alarms = device.get("alarms", [])
        if alarms:
            processed_device["alarm_count"] = len(alarms)
            
            # Categorize alarms
            error_alarms = [alarm for alarm in alarms if alarm.get("type") == "error"]
            warning_alarms = [alarm for alarm in alarms if alarm.get("type") == "warning"]
            
            if error_alarms:
                processed_device["alarm_status"] = "error"
                # Get the most recent or first error
                error_alarm = error_alarms[0]
                error_code = error_alarm.get("errorCode") or error_alarm.get("code")
                processed_device["error_code"] = error_code
                
                # Try multiple fields for error message
                error_message = (
                    error_alarm.get("message") or 
                    error_alarm.get("text") or 
                    error_alarm.get("default", {}).get("text") or
                    ERROR_CODES.get(error_code, "Unknown error")
                )
                processed_device["error_message"] = error_message
                
                # Store full error alarm data
                processed_device["error_alarm_data"] = error_alarm
                
            elif warning_alarms:
                processed_device["alarm_status"] = "warning"
                warning_alarm = warning_alarms[0]
                warning_code = warning_alarm.get("warningCode") or warning_alarm.get("code")
                processed_device["warning_code"] = warning_code
                processed_device["warning_message"] = (
                    warning_alarm.get("message") or 
                    warning_alarm.get("text") or 
                    warning_alarm.get("default", {}).get("text") or
                    "Warning condition detected"
                )
                processed_device["warning_alarm_data"] = warning_alarm
            else:
                processed_device["alarm_status"] = "unknown"
                
            # Store all alarm details for debugging
            processed_device["all_alarms"] = alarms
        
        # Extract component data with full detail preservation
        components = device.get("components", [])
        if isinstance(components, list):
            for component in components:
                component_id = component.get("id")
                if component_id is not None:  # Allow ID 0
                    processed_device["components"][str(component_id)] = {
                        "id": component_id,
                        "type": component.get("type"),
                        "status": component.get("status"),
                        "name": component.get("name"),
                        "model": component.get("model"),
                        "version": component.get("version"),
                        "data": component.get("data", {}),
                        "value": component.get("value"),
                        "reportedValue": component.get("reportedValue"),
                        "desiredValue": component.get("desiredValue"),
                        "ts": component.get("ts"),
                        "timestamp": component.get("timestamp"),
                        "unit": component.get("unit"),
                        "min": component.get("min"),
                        "max": component.get("max"),
                        "step": component.get("step"),
                        "readonly": component.get("readonly"),
                        "writable": component.get("writable"),
                        "category": component.get("category"),
                        "description": component.get("description"),
                        # Store full component data for debugging
                        "raw_data": component
                    }
        
        # Store any additional device fields that might contain useful data
        processed_device["raw_device_data"] = device
        
        return processed_device
    
    async def get_device_component_data(self, device_id: str, component_id: str) -> Optional[Dict[str, Any]]:
        """Get specific component data for a device."""
        try:
            # Check rate limiting
            if not self._check_rate_limit():
                _LOGGER.warning("Rate limit exceeded for component data request")
                return None
            
            if not await self.auth.refresh_token_if_needed():
                return None
            
            url = f"{API_DEVICES_URL}/{device_id}/components/{component_id}"
            headers = self.auth.get_auth_headers()
            
            # Record API call
            self._record_api_call()
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    _LOGGER.error("Failed to fetch component data: %s", response.status)
                    return None
                    
        except Exception as err:
            _LOGGER.error("Error fetching component data: %s", err)
            return None
    
    def get_device_error_info(self, device_id: str) -> Dict[str, Any]:
        """Get error information for a specific device."""
        device_data = self.devices.get(device_id, {})
        return {
            "error_code": device_data.get("error_code"),
            "error_message": device_data.get("error_message"),
            "alarm_status": device_data.get("alarm_status"),
            "alarm_count": device_data.get("alarm_count"),
            "alarms": device_data.get("alarms", [])
        }
    
    def get_device_connection_info(self, device_id: str) -> Dict[str, Any]:
        """Get connection information for a specific device."""
        device_data = self.devices.get(device_id, {})
        return {
            "connection_status": device_data.get("device_connection_status"),
            "session_id": device_data.get("device_session_id"),
            "connectivity_timestamp": device_data.get("device_connectivity_timestamp"),
            "first_connection": device_data.get("device_first_connection")
        }
    
    def get_api_management_info(self) -> Dict[str, Any]:
        """Get API management information."""
        return {
            "rate_limit": self.api_rate_limit,
            "last_api_call": self.last_api_call.isoformat() if self.last_api_call else None,
            "api_calls_in_last_minute": len(self.api_calls),
            "next_update": self.next_update.isoformat() if self.next_update else None,
        }
    
    def _process_error_information(self) -> None:
        """Process error information from device data."""
        self.error_information = {}
        
        # Get device_id from config entry
        device_id = None
        if self.config_entry:
            device_id = self.config_entry.data.get(CONF_DEVICE_ID)
        
        # If we have a specific device_id from config, use that
        if self.devices and device_id and device_id in self.devices:
            device_data = self.devices.get(device_id, {})
            if isinstance(device_data, dict):
                # Extract error information
                error_code = device_data.get('error_code')
                error_message = device_data.get('error_message')
                alarm_status = device_data.get('alarm_status')
                alarm_count = device_data.get('alarm_count')
                
                if error_code or error_message or alarm_status:
                    self.error_information = {
                        'error_code': error_code,
                        'error_message': error_message,
                        'alarm_status': alarm_status,
                        'alarm_count': alarm_count,
                        'device_id': device_id,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Map error codes to descriptions
                    if error_code and error_code in ERROR_CODES:
                        self.error_information['error_description'] = ERROR_CODES[error_code]
                    else:
                        self.error_information['error_description'] = "Unknown error"
        
        # If no specific device_id or no errors found, check all devices
        elif self.devices:
            for dev_id, device_data in self.devices.items():
                if isinstance(device_data, dict):
                    error_code = device_data.get('error_code')
                    error_message = device_data.get('error_message')
                    alarm_status = device_data.get('alarm_status')
                    alarm_count = device_data.get('alarm_count')
                    
                    if error_code or error_message or alarm_status:
                        self.error_information = {
                            'error_code': error_code,
                            'error_message': error_message,
                            'alarm_status': alarm_status,
                            'alarm_count': alarm_count,
                            'device_id': dev_id,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        # Map error codes to descriptions
                        if error_code and error_code in ERROR_CODES:
                            self.error_information['error_description'] = ERROR_CODES[error_code]
                        else:
                            self.error_information['error_description'] = "Unknown error"
                        break  # Use the first device with errors
    
    # New API fetch methods for additional endpoints
    
    async def _fetch_user_profile_data(self) -> None:
        """Fetch user profile data from Fluidra API."""
        try:
            # Check rate limiting
            if not self._check_rate_limit():
                _LOGGER.warning("Rate limit exceeded for user profile data request")
                return
            
            headers = self.auth.get_auth_headers()
            
            # Record API call
            self._record_api_call()
            
            async with self.session.get(API_ENDPOINT_USER_PROFILE, headers=headers) as response:
                if response.status == 200:
                    self.user_profile_data = await response.json()
                    _LOGGER.debug("Successfully fetched user profile data")
                else:
                    _LOGGER.error("Failed to fetch user profile data: %s", response.status)
                    self.user_profile_data = {}
        except Exception as err:
            _LOGGER.error("Error fetching user profile data: %s", err)
            self.user_profile_data = {}
    
    async def _fetch_pool_status_data(self, pool_id: str) -> None:
        """Fetch pool status data from Fluidra API."""
        try:
            url = API_ENDPOINT_POOL_STATUS.format(pool_id=pool_id)
            headers = self.auth.get_auth_headers()
            
            # Record API call
            self._record_api_call()
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    self.pool_status_data = await response.json()
                    _LOGGER.debug("Successfully fetched pool status data for pool %s", pool_id)
                elif response.status == 403:
                    _LOGGER.warning("Pool status endpoint not accessible (403) - this endpoint may not be available for all users")
                    self.pool_status_data = {}
                else:
                    _LOGGER.error("Failed to fetch pool status data: %s", response.status)
                    self.pool_status_data = {}
        except Exception as err:
            _LOGGER.error("Error fetching pool status data: %s", err)
            self.pool_status_data = {}
    
    async def _fetch_user_pools_data(self) -> None:
        """Fetch user pools data from Fluidra API."""
        try:
            headers = self.auth.get_auth_headers()
            
            # Record API call
            self._record_api_call()
            
            async with self.session.get(API_ENDPOINT_USER_POOLS, headers=headers) as response:
                if response.status == 200:
                    user_pools_response = await response.json()
                    self.user_pools_data = self._process_user_pools_data(user_pools_response)
                    _LOGGER.debug("Successfully fetched user pools data")
                elif response.status == 403:
                    _LOGGER.warning("User pools endpoint not accessible (403) - this endpoint may not be available for all users")
                    self.user_pools_data = {}
                else:
                    _LOGGER.error("Failed to fetch user pools data: %s", response.status)
                    self.user_pools_data = {}
        except Exception as err:
            _LOGGER.error("Error fetching user pools data: %s", err)
            self.user_pools_data = {}
    
    def _process_user_pools_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and extract relevant data from user pools response."""
        processed_data = {}
        
        try:
            if isinstance(raw_data, list):
                for user_pool in raw_data:
                    pool_id = user_pool.get("poolId")
                    if pool_id:
                        processed_data[pool_id] = {
                            "pool_id": pool_id,
                            "access_level": user_pool.get("accessLevel"),
                            "permissions": user_pool.get("permissions"),
                            "role": user_pool.get("role"),
                            "owner": user_pool.get("owner"),
                            "access_granted_date": user_pool.get("accessGrantedDate"),
                            "last_accessed": user_pool.get("lastAccessed"),
                        }
            elif "data" in raw_data and isinstance(raw_data["data"], list):
                for user_pool in raw_data["data"]:
                    pool_id = user_pool.get("poolId")
                    if pool_id:
                        processed_data[pool_id] = {
                            "pool_id": pool_id,
                            "access_level": user_pool.get("accessLevel"),
                            "permissions": user_pool.get("permissions"),
                            "role": user_pool.get("role"),
                            "owner": user_pool.get("owner"),
                            "access_granted_date": user_pool.get("accessGrantedDate"),
                            "last_accessed": user_pool.get("lastAccessed"),
                        }
            
            _LOGGER.debug("Processed %d user pools", len(processed_data))
            
        except Exception as err:
            _LOGGER.error("Error processing user pools data: %s", err)
            processed_data = {}
        
        return processed_data
    
    async def _fetch_device_components_data(self, device_id: str) -> None:
        """Fetch device components data from Fluidra API."""
        try:
            url = API_ENDPOINT_DEVICE_COMPONENTS.format(device_id=device_id)
            headers = self.auth.get_auth_headers()
            
            _LOGGER.info("Fetching device components from URL: %s", url)
            _LOGGER.debug("Headers: %s", headers)
            
            # Record API call
            self._record_api_call()
            
            async with self.session.get(url, headers=headers) as response:
                _LOGGER.info("Device components response status: %s", response.status)
                
                if response.status == 200:
                    components_response = await response.json()
                    _LOGGER.info("Device components response: %s", components_response)
                    processed_data = self._process_device_components_data(components_response)
                    
                    # Store the data organized by device ID
                    if not hasattr(self, 'device_components_data') or self.device_components_data is None:
                        self.device_components_data = {}
                    self.device_components_data[device_id] = processed_data
                    
                    _LOGGER.info("Successfully fetched device components data for device %s", device_id)
                elif response.status == 403:
                    _LOGGER.warning("Device components endpoint not accessible (403) - this endpoint may not be available for all users")
                    if not hasattr(self, 'device_components_data') or self.device_components_data is None:
                        self.device_components_data = {}
                    self.device_components_data[device_id] = {}
                elif response.status == 400:
                    _LOGGER.warning("Device components endpoint returned 400 - this endpoint may not be available for all users")
                    response_text = await response.text()
                    _LOGGER.warning("Device components 400 response: %s", response_text)
                    if not hasattr(self, 'device_components_data') or self.device_components_data is None:
                        self.device_components_data = {}
                    self.device_components_data[device_id] = {}
                else:
                    response_text = await response.text()
                    _LOGGER.error("Failed to fetch device components data: %s - %s", response.status, response_text)
                    if not hasattr(self, 'device_components_data') or self.device_components_data is None:
                        self.device_components_data = {}
                    self.device_components_data[device_id] = {}
        except Exception as err:
            _LOGGER.error("Error fetching device components data: %s", err)
            if not hasattr(self, 'device_components_data') or self.device_components_data is None:
                self.device_components_data = {}
            self.device_components_data[device_id] = {}
    
    def _process_device_components_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and extract relevant data from device components response."""
        processed_data = {}
        
        try:
            if isinstance(raw_data, list):
                # API returns a simple array of components with id, reportedValue, ts
                for component in raw_data:
                    component_id = component.get("id")
                    if component_id is not None:
                        processed_data[str(component_id)] = {
                            "id": component_id,
                            "reportedValue": component.get("reportedValue"),
                            "ts": component.get("ts"),
                            # Add the component data directly for easy access
                            **component
                        }
            elif "data" in raw_data and isinstance(raw_data["data"], list):
                # If response has a data field with list
                for component in raw_data["data"]:
                    component_id = component.get("id")
                    if component_id is not None:
                        processed_data[str(component_id)] = {
                            "id": component_id,
                            "reportedValue": component.get("reportedValue"),
                            "ts": component.get("ts"),
                            # Add the component data directly for easy access
                            **component
                        }
            
            _LOGGER.info("Processed %d device components", len(processed_data))
            _LOGGER.debug("Component IDs found: %s", list(processed_data.keys()))
            
        except Exception as err:
            _LOGGER.error("Error processing device components data: %s", err)
            processed_data = {}
        
        return processed_data
    
    async def _fetch_device_uiconfig_data(self, device_id: str) -> None:
        """Fetch device UI configuration data from Fluidra API."""
        try:
            url = API_ENDPOINT_DEVICE_UICONFIG.format(device_id=device_id)
            headers = self.auth.get_auth_headers()
            
            # Record API call
            self._record_api_call()
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    uiconfig_response = await response.json()
                    self.device_uiconfig_data = self._process_device_uiconfig_data(uiconfig_response)
                    _LOGGER.debug("Successfully fetched device UI config data for device %s", device_id)
                elif response.status == 403:
                    _LOGGER.warning("Device UI config endpoint not accessible (403) - this endpoint may not be available for all users")
                    self.device_uiconfig_data = {}
                elif response.status == 400:
                    _LOGGER.warning("Device UI config endpoint returned 400 - this endpoint may not be available for all users")
                    self.device_uiconfig_data = {}
                else:
                    _LOGGER.error("Failed to fetch device UI config data: %s", response.status)
                    self.device_uiconfig_data = {}
        except Exception as err:
            _LOGGER.error("Error fetching device UI config data: %s", err)
            self.device_uiconfig_data = {}
    
    def _process_device_uiconfig_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process device UI config data."""
        processed_data = {}
        
        if isinstance(raw_data, dict):
            # Extract relevant UI configuration data
            processed_data = {
                'ui_config': raw_data.get('uiConfig', {}),
                'features': raw_data.get('features', {}),
                'controls': raw_data.get('controls', {}),
                'display_options': raw_data.get('displayOptions', {}),
                'language': raw_data.get('language', 'en'),
                'theme': raw_data.get('theme', 'default'),
                'notifications': raw_data.get('notifications', {}),
                'automation_rules': raw_data.get('automationRules', {}),
                'schedule_settings': raw_data.get('scheduleSettings', {}),
                'maintenance_reminders': raw_data.get('maintenanceReminders', {}),
                'energy_settings': raw_data.get('energySettings', {}),
            }
        
        return processed_data
    
    async def set_component_value(self, device_id: str, component_id: str, value: Any) -> bool:
        """Set a generic component value via API with desiredValue only."""
        try:
            if not self._check_rate_limit():
                _LOGGER.warning("API call skipped due to rate limiting.")
                return False
            if not await self.auth.refresh_token_if_needed():
                _LOGGER.error("Authentication failed for component value set.")
                return False
            if self.device_components_data and device_id in self.device_components_data:
                device_components = self.device_components_data[device_id]
                component_data = device_components.get(str(component_id)) or device_components.get(component_id)
                _LOGGER.debug("[Fluidra Debug] set_component_value: Available component IDs: %s", list(device_components.keys()))
                if component_data:
                    payload = {"desiredValue": value}
                    url = API_ENDPOINT_SET_COMPONENT_VALUE.format(
                        device_id=device_id,
                        component_id=component_id
                    )
                    headers = self.auth.get_auth_headers()
                    headers['Content-Type'] = 'application/json; charset=utf-8'
                    _LOGGER.info("[Fluidra Debug] Setting component %s value to %s via PUT to %s with payload: %s", 
                               component_id, value, url, payload)
                    self._record_api_call()
                    async with self.session.put(url, json=payload, headers=headers) as response:
                        response_text = await response.text()
                        _LOGGER.info("[Fluidra Debug] Component value set response status: %s, body: %s", response.status, response_text)
                        if response.status == 200:
                            _LOGGER.info("Successfully set component value via PUT")
                            await self.schedule_quick_update()
                            return True
                        else:
                            _LOGGER.error("Failed to set component value via PUT: %s - %s", 
                                         response.status, response_text)
                            return False
                else:
                    _LOGGER.error("Component %s not found in device %s", component_id, device_id)
                    return False
            else:
                _LOGGER.error("No device components data available for device %s", device_id)
                return False
        except Exception as err:
            _LOGGER.error("Error setting component value: %s", err)
            return False
    
    async def set_temperature_value(self, device_id: str, component_id: str, desired_value: int) -> bool:
        """Set temperature value via API with desiredValue only."""
        try:
            if not self._check_rate_limit():
                _LOGGER.warning("API call skipped due to rate limiting.")
                return False
            if not await self.auth.refresh_token_if_needed():
                _LOGGER.error("Authentication failed for temperature value set.")
                return False
            if self.device_components_data and device_id:
                device_components = self.device_components_data.get(device_id, {})
                component_data = device_components.get(str(component_id)) or device_components.get(component_id)
                _LOGGER.debug("[Fluidra Debug] set_temperature_value: Available component IDs: %s", list(device_components.keys()))
                if isinstance(component_data, dict):
                    actual_component_id = component_id
                    payload = {"desiredValue": desired_value}
                    url = API_ENDPOINT_SET_COMPONENT_VALUE.format(
                        device_id=device_id,
                        component_id=actual_component_id
                    )
                    headers = self.auth.get_auth_headers()
                    headers['Content-Type'] = 'application/json; charset=utf-8'
                    _LOGGER.info("[Fluidra Debug] Setting temperature value via PUT to %s with payload: %s", url, payload)
                    self._record_api_call()
                    async with self.session.put(url, headers=headers, json=payload) as response:
                        response_text = await response.text()
                        _LOGGER.info("[Fluidra Debug] Temperature value set response status: %s, body: %s", response.status, response_text)
                        if response.status == 200:
                            _LOGGER.info("Successfully set temperature value via PUT")
                            await self.schedule_quick_update()
                            return True
                        else:
                            _LOGGER.error("Failed to set temperature value. Status: %s, Response: %s", response.status, response_text)
                            return False
                else:
                    _LOGGER.error("Invalid component data format for component %s", component_id)
                    return False
            else:
                _LOGGER.error("No device components data available for device %s", device_id)
                return False
        except Exception as err:
            _LOGGER.error("Error setting temperature value: %s", err)
            return False
    
    async def set_power_value(self, device_id: str, component_id: str, desired_value: int) -> bool:
        """Set power on/off value via API with desiredValue only."""
        try:
            if not self._check_rate_limit():
                _LOGGER.warning("API call skipped due to rate limiting.")
                return False
            if not await self.auth.refresh_token_if_needed():
                _LOGGER.error("Authentication failed for power value set.")
                return False
            # Get the component data to find the component ID
            if self.device_components_data and device_id:
                device_components = self.device_components_data.get(device_id, {})
                component_data = device_components.get(str(component_id)) or device_components.get(component_id)
                _LOGGER.debug("[Fluidra Debug] set_power_value: Available component IDs: %s", list(device_components.keys()))
                if isinstance(component_data, dict):
                    actual_component_id = component_id
                    payload = {"desiredValue": desired_value}
                    url = API_ENDPOINT_SET_COMPONENT_VALUE.format(
                        device_id=device_id,
                        component_id=actual_component_id
                    )
                    headers = self.auth.get_auth_headers()
                    headers['Content-Type'] = 'application/json; charset=utf-8'
                    _LOGGER.info("[Fluidra Debug] Setting power value via PUT to %s with payload: %s", url, payload)
                    self._record_api_call()
                    async with self.session.put(url, headers=headers, json=payload) as response:
                        response_text = await response.text()
                        _LOGGER.info("[Fluidra Debug] Power value set response status: %s, body: %s", response.status, response_text)
                        if response.status == 200:
                            _LOGGER.info("Successfully set power value via PUT")
                            await self.schedule_quick_update()
                            return True
                        else:
                            _LOGGER.error("Failed to set power value. Status: %s, Response: %s", response.status, response_text)
                            return False
                else:
                    _LOGGER.error("Invalid component data format for component %s", component_id)
                    return False
            else:
                _LOGGER.error("No device components data available for device %s", device_id)
                return False
        except Exception as err:
            _LOGGER.error("Error setting power value: %s", err)
            return False
    
    def get_device_by_serial_number(self, serial_number: str) -> Optional[Dict[str, Any]]:
        """Find a device by its serial number."""
        if not self.devices:
            return None
        
        for device_id, device_data in self.devices.items():
            device_serial = (device_data.get("serial_number") or 
                           device_data.get("SerialNumber") or 
                           device_data.get("sn"))
            if device_serial == serial_number:
                return device_data
        
        return None
    
    def get_device_id_by_serial_number(self, serial_number: str) -> Optional[str]:
        """Find a device ID by its serial number."""
        if not self.devices:
            return None
        
        for device_id, device_data in self.devices.items():
            device_serial = (device_data.get("serial_number") or 
                           device_data.get("SerialNumber") or 
                           device_data.get("sn"))
            if device_serial == serial_number:
                return device_id
        
        return None 