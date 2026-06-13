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
from homeassistant.util import slugify
from .const import DOMAIN, REGIONS, CONF_PLANT_ID, CONF_REGION

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up all Alpsolar sensors with dynamic, robust object handshaking."""
    coordinator = AlpsolarCoordinator(hass, entry.data)
    await coordinator.async_config_entry_first_refresh()
    
    all_entities = []
    device_name = "Alpsolar Inverter"
    plant_id = coordinator.config[CONF_PLANT_ID]

    # 1. Instantiate Parent Power Sensors as discrete objects
    solar_pv_sensor = AlpsolarSensor(coordinator, "pvPower", "Solar PV Power", SensorDeviceClass.POWER, "W", device_name)
    house_load_sensor = AlpsolarSensor(coordinator, "loadOrEpsPower", "House Load", SensorDeviceClass.POWER, "W", device_name)
    grid_power_sensor = AlpsolarSensor(coordinator, "gridOrMeterPower", "Grid Power", SensorDeviceClass.POWER, "W", device_name)
    batt_sensor = AlpsolarSensor(coordinator, "battPower", "Battery Power", SensorDeviceClass.POWER, "W", device_name)
    soc_sensor = AlpsolarSensor(coordinator, "soc", "Battery SOC", SensorDeviceClass.BATTERY, "%", device_name)
    
    # 2. Instantiate Split Battery Power Sensors
    batt_in_sensor = BatterySplitSensor(coordinator, "in", device_name)
    batt_out_sensor = BatterySplitSensor(coordinator, "out", device_name)
    
    # Add parent tracking array
    all_entities.extend([
        solar_pv_sensor, 
        house_load_sensor, 
        grid_power_sensor,
        batt_sensor, 
        soc_sensor, 
        batt_in_sensor, 
        batt_out_sensor
    ])

    # 3. Dynamic Energy Sensor Creation via Direct Property Mapping
    # This reads the live runtime .entity_id directly, remaining immune to renames.
    energy_targets = [
        (solar_pv_sensor, "Solar PV Power Energy"),
        (house_load_sensor, "House Load Energy"),
        (grid_power_sensor, "Grid Power Energy"),
        (batt_in_sensor, "Battery Energy In"),
        (batt_out_sensor, "Battery Energy Out"),
    ]

    for source_sensor, energy_name in energy_targets:
        all_entities.append(
            AlpsolarEnergySensor(
                hass=hass,
                source_sensor=source_sensor,  # Pass the entire live sensor object
                name=energy_name,
                unique_id=f"alps_{plant_id}_{slugify(energy_name)}",
                plant_id=plant_id,
                device_name=device_name
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
                
                login_data = {
                    "username": self.config["username"], 
                    "password": self.config["password"], 
                    "grant_type": "password", 
                    "client_id": "csp-web"
                }
                
                token_r = requests.post(f"{base_url}/oauth/token", json=login_data, timeout=15)
                token_r.raise_for_status()
                token = token_r.json().get("data", {}).get("access_token")
                
                if not token:
                    raise UpdateFailed("Failed to obtain access token from local API shard.")
                
                headers = {"Authorization": f"Bearer {token}"}
                plant_id = self.config[CONF_PLANT_ID]
                list_url = f"{base_url}/api/v1/plant/station/list"
                
                res = requests.get(list_url, headers=headers, timeout=15)
                res.raise_for_status()
                
                stations = res.json().get("data", {}).get("list", [])
                for station in stations:
                    if stroke := str(station.get("plantId")) == str(plant_id):
                        return station
                return {}
            except Exception as err:
                raise UpdateFailed(f"API Error during telemetry sync: {err}")
        return await self.hass.async_add_executor_job(fetch)

class AlpsolarSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, name, device_class, unit, device_name):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self.unique_id = f"alps_{coordinator.config[CONF_PLANT_ID]}_{key.lower()}"
        self._attr_unique_id = self.unique_id
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.config[CONF_PLANT_ID])}, "name": device_name}

    @property
    def native_value(self):
        if self.coordinator.data:
            val = self.coordinator.data.get(self._key)
            try: return float(val) if val is not None else 0.0
            except: return 0.0
        return 0.0

class BatterySplitSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, mode, device_name):
        super().__init__(coordinator)
        self._mode = mode
        self._attr_name = f"Battery Power {mode.capitalize()}"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = "W"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self.unique_id = f"alps_{coordinator.config[CONF_PLANT_ID]}_batt_p_{mode}"
        self._attr_unique_id = self.unique_id
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.config[CONF_PLANT_ID])}, "name": device_name}

    @property
    def native_value(self):
        val = self.coordinator.data.get("battPower", 0)
        try:
            val = float(val)
            if self._mode == "in": return max(0, val)
            else: return max(0, -val)
        except: return 0.0

class AlpsolarEnergySensor(IntegrationSensor):
    def __init__(self, hass, source_sensor, name, unique_id, plant_id, device_name):
        self._source_sensor = source_sensor
        super().__init__(
            hass=hass, 
            integration_method="left", 
            name=name, 
            round_digits=2,
            source_entity=source_sensor.entity_id, # Safely populated during registration
            unique_id=unique_id, 
            unit_prefix="k",
            unit_time=UnitOfTime.HOURS, 
            max_sub_interval=None
        )
        self._attr_device_info = {"identifiers": {(DOMAIN, plant_id)}, "name": device_name}

    async def async_added_to_hass(self):
        """Handle tracking fallback dynamically if entity_id strings change."""
        self._source_entity = self._source_sensor.entity_id
        await super().async_added_to_hass()
