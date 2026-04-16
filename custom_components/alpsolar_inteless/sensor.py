import logging
from datetime import timedelta
import requests
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.integration.sensor import IntegrationSensor
from homeassistant.const import UnitOfTime
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
    UpdateFailed,
)
from .const import DOMAIN, REGIONS, CONF_PLANT_ID, CONF_REGION

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Alpsolar sensors with forced entity IDs."""
    coordinator = AlpsolarCoordinator(hass, entry.data)
    await coordinator.async_config_entry_first_refresh()
    
    all_entities = []
    power_configs = [
        ("pvPower", "Solar PV Power", SensorDeviceClass.POWER, "W"),
        ("loadOrEpsPower", "House Load", SensorDeviceClass.POWER, "W"),
        ("battPower", "Battery Power", SensorDeviceClass.POWER, "W"),
        ("soc", "Battery SOC", SensorDeviceClass.BATTERY, "%"),
        ("gridOrMeterPower", "Grid Power", SensorDeviceClass.POWER, "W"),
    ]
    
    for key, name, dev_class, unit in power_configs:
        # Create the Power Sensor
        ps = AlpsolarSensor(coordinator, key, name, dev_class, unit)
        all_entities.append(ps)
        
        # Create the Energy Sensor if applicable
        if key in ["pvPower", "loadOrEpsPower", "gridOrMeterPower"]:
            # We reference the exact entity_id we forced in the AlpsolarSensor class
            source_id = f"sensor.alps_{coordinator.config[CONF_PLANT_ID]}_{key.lower()}"
            all_entities.append(
                AlpsolarEnergySensor(
                    hass=hass,
                    source_entity=source_id,
                    name=f"{name} Energy",
                    unique_id=f"{ps.unique_id}_energy",
                    plant_id=coordinator.config[CONF_PLANT_ID]
                )
            )
    
    async_add_entities(all_entities)

class AlpsolarCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=60))
        self.config = config

    async def _async_update_data(self):
        def fetch():
            try:
                region_name = self.config.get(CONF_REGION, "Europe")
                base_url = REGIONS.get(region_name, "https://euapi.inteless.com")
                login_data = {"username": self.config["username"], "password": self.config["password"], "grant_type": "password", "client_id": "csp-web"}
                token_r = requests.post(f"{base_url}/oauth/token", json=login_data, timeout=15)
                token = token_r.json().get("data", {}).get("access_token")
                res = requests.get(f"{base_url}/api/v1/plant/energy/{self.config[CONF_PLANT_ID]}/flow", 
                                   headers={"Authorization": f"Bearer {token}"}, timeout=15)
                return res.json().get("data") or {}
            except Exception as err:
                raise UpdateFailed(f"API Error: {err}")
        return await self.hass.async_add_executor_job(fetch)

class AlpsolarSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, name, device_class, unit):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        # FORCING THE ENTITY ID: This ensures the Energy sensor always finds it.
        plant_id = coordinator.config[CONF_PLANT_ID]
        self.unique_id = f"alps_{plant_id}_{key.lower()}"
        self.entity_id = f"sensor.{self.unique_id}"
        
        self._attr_unique_id = self.unique_id
        self._attr_device_info = {"identifiers": {(DOMAIN, plant_id)}, "name": "Alpsolar Inverter"}

    @property
    def native_value(self):
        if self.coordinator.data:
            val = self.coordinator.data.get(self._key)
            try:
                return float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        return 0.0

class AlpsolarEnergySensor(IntegrationSensor):
    def __init__(self, hass, source_entity, name, unique_id, plant_id):
        super().__init__(
            hass=hass,
            integration_method="left",
            name=name,
            round_digits=2,
            source_entity=source_entity,
            unique_id=unique_id,
            unit_prefix="k",
            unit_time=UnitOfTime.HOURS,
            max_sub_interval=None
        )
        self._attr_device_info = {"identifiers": {(DOMAIN, plant_id)}, "name": "Alpsolar Inverter"}
