import logging
from datetime import timedelta
import requests
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
    UpdateFailed,
)
from .const import DOMAIN, REGIONS, CONF_PLANT_ID, CONF_REGION

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Alpsolar sensors based on a config entry."""
    coordinator = AlpsolarCoordinator(hass, entry.data)
    
    # Trigger the first refresh
    await coordinator.async_config_entry_first_refresh()
    
    sensors = [
        AlpsolarSensor(coordinator, "pvPower", "Solar PV Power", SensorDeviceClass.POWER, "W"),
        AlpsolarSensor(coordinator, "loadOrEpsPower", "House Load", SensorDeviceClass.POWER, "W"),
        AlpsolarSensor(coordinator, "battPower", "Battery Power", SensorDeviceClass.POWER, "W"),
        AlpsolarSensor(coordinator, "soc", "Battery SOC", SensorDeviceClass.BATTERY, "%"),
        AlpsolarSensor(coordinator, "gridOrMeterPower", "Grid Power", SensorDeviceClass.POWER, "W"),
    ]
    
    async_add_entities(sensors)

class AlpsolarCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Inteless API."""

    def __init__(self, hass, config):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.config = config

    async def _async_update_data(self):
        """Fetch data from the API shard selected by the user."""
        def fetch():
            try:
                # Identify the correct API URL based on the user's region selection
                region_name = self.config.get(CONF_REGION, "Europe")
                base_url = REGIONS.get(region_name, "https://euapi.inteless.com")
                
                # 1. Get Access Token
                login_data = {
                    "username": self.config["username"],
                    "password": self.config["password"],
                    "grant_type": "password",
                    "client_id": "csp-web"
                }
                
                token_response = requests.post(f"{base_url}/oauth/token", json=login_data, timeout=15)
                token_response.raise_for_status()
                token = token_response.json().get("data", {}).get("access_token")
                
                if not token:
                    raise UpdateFailed("Failed to obtain access token from Inteless")

                # 2. Fetch Flow Data
                headers = {"Authorization": f"Bearer {token}"}
                plant_id = self.config[CONF_PLANT_ID]
                flow_url = f"{base_url}/api/v1/plant/energy/{plant_id}/flow"
                
                res = requests.get(flow_url, headers=headers, timeout=15)
                res.raise_for_status()
                
                data = res.json().get("data")
                if not data:
                    _LOGGER.warning("No data returned for Plant ID %s", plant_id)
                    return {}
                    
                return data

            except requests.exceptions.RequestException as err:
                raise UpdateFailed(f"Error communicating with Inteless API: {err}")
            except Exception as err:
                raise UpdateFailed(f"Unexpected error: {err}")

        return await self.hass.async_add_executor_job(fetch)

class AlpsolarSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Alpsolar sensor."""

    def __init__(self, coordinator, key, name, device_class, unit):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        # Unique ID prevents duplicate entities if the integration is reloaded
        self._attr_unique_id = f"alps_{coordinator.config[CONF_PLANT_ID]}_{key}"
        # Links the sensor to the "Device" in HA UI
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config[CONF_PLANT_ID])},
            "name": "Alpsolar Inverter",
            "manufacturer": "Alpsolar / E-Linter",
        }

    @property
    def native_value(self):
        """Return the state of the sensor from the coordinator data."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._key)
        return None
