"""Sensores nativos de KinderClose."""
from datetime import date

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTime
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PUPIL_ID, DOMAIN

SENSORS = {
    "ultima_ficha": "Última ficha", "asistencia": "Asistencia",
    "entrada": "Entrada", "salida": "Salida", "desayuno": "Desayuno",
    "primero": "Primero", "segundo": "Segundo", "postre": "Postre",
    "merienda": "Merienda", "sueno": "Sueño", "deposiciones": "Deposiciones",
}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(KinderCloseSensor(entry.runtime_data, key, name) for key, name in SENSORS.items())


class KinderCloseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self.key = key
        pupil_id = coordinator.entry.data[CONF_PUPIL_ID]
        self._attr_unique_id = f"{pupil_id}_{key}"
        self._attr_name = name
        self.entity_id = f"sensor.kinderclose_{pupil_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, pupil_id)}, name=f"KinderClose {pupil_id}", manufacturer="KinderClose", entry_type=DeviceEntryType.SERVICE)
        if key == "ultima_ficha":
            self._attr_device_class = SensorDeviceClass.DATE
        elif key == "sueno":
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES

    @property
    def native_value(self):
        record = self.coordinator.data["fichas"][0]
        if self.key == "ultima_ficha":
            return date.fromisoformat(record["fecha"])
        if self.key == "asistencia":
            return "ausente" if record["presencia"]["ausente"] in ("Sí", "Si") else "presente"
        if self.key in ("entrada", "salida"):
            return record["presencia"].get("hora_" + self.key)
        if self.key == "sueno":
            return record["sueno_minutos"]
        if self.key == "deposiciones":
            return len(record["deposiciones"])
        return record["comidas"].get(self.key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        record = data["fichas"][0]
        attributes = {"fecha_ficha": record["fecha"], "url_ficha": record["url"]}
        if self.key == "ultima_ficha":
            attributes.update(fichas=data["fichas"], consultado_en=data["consultado_en"])
        elif self.key == "sueno":
            attributes["sesiones"] = record["sueno"]
        elif self.key == "deposiciones":
            attributes["detalles"] = record["deposiciones"]
        return attributes
