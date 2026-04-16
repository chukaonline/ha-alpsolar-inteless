import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN, CONF_PLANT_ID, BASE_URL
import requests

class AlpsolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Alpsolar Inteless."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate the credentials by attempting a login
            valid = await self.hass.async_add_executor_job(
                self._validate_login, 
                user_input[CONF_USERNAME], 
                user_input[CONF_PASSWORD]
            )

            if valid:
                return self.async_create_entry(
                    title=f"Alpsolar ({user_input[CONF_PLANT_ID]})", 
                    data=user_input
                )
            else:
                errors["base"] = "invalid_auth"

        # Form schema for the UI
        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Required(CONF_PLANT_ID): cv.string,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    def _validate_login(self, username, password):
        """Check if we can login to the Inteless API."""
        login_data = {
            "username": username,
            "password": password,
            "grant_type": "password",
            "client_id": "csp-web"
        }
        try:
            r = requests.post(f"{BASE_URL}/oauth/token", json=login_data, timeout=10)
            return r.status_code == 200 and "access_token" in r.json().get("data", {})
        except Exception:
            return False