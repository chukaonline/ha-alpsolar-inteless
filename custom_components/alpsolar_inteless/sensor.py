import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from .const import DOMAIN, BASE_URL
import requests

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = AlpsolarCoordinator(hass, entry.data)
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
    def __init__(self, hass, config):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=60))
        self.config = config

    async def _async_update_data(self):
        # This handles the API logic we perfected in AppDaemon
        def fetch():
            login_data = {"username": self.config["username"], "password": self.config["password"], "grant_type": "password", "client_id": "csp-web"}
            r = requests.post(f"{BASE_URL}/oauth/token", json=login_data, timeout=10)
            token = r.json().get("data", {}).get("access_token")
            
            url = f"{BASE_URL}/api/v1/plant/energy/{self.config['plant_id']}/flow"
            res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
            return res.json().get("data")
            
        return await self.hass.async_add_executor_job(fetch)

class AlpsolarSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, name, device_class, unit):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"alps_{coordinator.config['plant_id']}_{key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)