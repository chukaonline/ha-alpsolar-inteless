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
from .const import DOMAIN, REGIONS, DATA_URL, CONF_PLANT_ID, CONF_REGION

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up all Alpsolar sensors including Battery In/Out logic."""
    coordinator = AlpsolarCoordinator(hass, entry.data)
    await coordinator.async_config_entry_first_refresh()
    
    all_entities = []
    device_name = "Alpsolar Inverter"
    plant_id = coordinator.config[CONF_PLANT_ID]

    # 1. Base Power Sensors
    power_configs = [
        ("pvPower", "Solar PV Power", SensorDeviceClass.POWER, "W"),
        ("loadOrEpsPower", "House Load", SensorDeviceClass.POWER, "W"),
        ("battPower", "Battery Power", SensorDeviceClass.POWER, "W"),
        ("soc", "Battery SOC", SensorDeviceClass.BATTERY, "%"),
        ("gridOrMeterPower", "Grid Power", SensorDeviceClass.POWER, "W"),
    ]
    
    for key, name, dev_class, unit in power_configs:
        ps = AlpsolarSensor(coordinator, key, name, dev_class, unit, device_name)
        all_entities.append(ps)

    # 2. Split Battery Power Sensors (Charging vs Discharging)
    batt_in_power = BatterySplitSensor(coordinator, "in", device_name)
    batt_out_power = BatterySplitSensor(coordinator, "out", device_name)
    all_entities.extend([batt_in_power, batt_out_power])

    # 3. Energy Sensors (Riemann Sum)
    energy_targets = [
        ("solar_pv_power", "Solar PV Power Energy"),
        ("house_load", "House Load Energy"),
        ("grid_power", "Grid Power Energy"),
        ("battery_power_in", "Battery Energy In"),
        ("battery_power_out", "Battery Energy Out"),
    ]

    for slug_part, energy_name in energy_targets:
        source_id = f"sensor.{slugify(f'{device_name} {slug_part}')}"
        all_entities.append(
            AlpsolarEnergySensor(
                hass=hass,
                source_entity=source_id,
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
                auth_url = REGIONS.get(region_name, "https://euapi.inteless.com")
                
                # 1. Authenticate against regional endpoint
                login_data = {
                    "username": self.config["username"], 
                    "password": self.config["password"], 
                    "grant_type": "password", 
                    "client_id": "csp-web"
                }
                
                token_r = requests.post(f"{auth_url}/oauth/token", json=login_data, timeout=15)
                token_r.raise_for_status()
                token = token_r.json().get("data", {}).get("access_token")
                
                if not token:
                    raise UpdateFailed("Failed to obtain access token from regional endpoint")
                
                # 2. Fetch actual inverter data from global domain (As per Issue #1)
                headers = {"Authorization": f"Bearer {token}"}
                plant_id = self.config[CONF_PLANT_ID]
                flow_url = f"{DATA_URL}/api/v1/plant/energy/{plant_id}/flow"
                
                res = requests.get(flow_url, headers=headers, timeout=15)
                res.raise_for_status()
                return res.json().get("data") or {}
                
            except Exception as err:
                raise UpdateFailed(f"API Error during endpoint separation: {err}")
                
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
            if self._mode == "in":
                return max(0, val)
            else:
                return max(0, -val)
        except: return 0.0

class AlpsolarEnergySensor(IntegrationSensor):
    def __init__(self, hass, source_entity, name, unique_id, plant_id, device_name):
        super().__init__(
            hass=hass, integration_method="left", name=name, round_digits=2,
            source_entity=source_entity, unique_id=unique_id, unit_prefix="k",
            unit_time=UnitOfTime.HOURS, max_sub_interval=None
        )
        self._attr_device_info = {"identifiers": {(DOMAIN, plant_id)}, "name": device_name}
