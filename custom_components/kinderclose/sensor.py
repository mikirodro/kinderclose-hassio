"""Sensores nativos de KinderClose."""
from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PUPIL_ID, DOMAIN

# Los nombres visibles están en strings.json y translations/, bajo entity.sensor.<clave>.
SENSORS = (
    "ultima_ficha", "asistencia", "entrada", "salida", "desayuno", "primero",
    "segundo", "postre", "merienda", "sueno", "deposiciones", "biberones", "recordatorios",
)
MEALS = ("desayuno", "primero", "segundo", "postre", "merienda")

# Solo el coordinador consulta KinderClose; las entidades no hacen E/S propia.
PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(KinderCloseSensor(entry.runtime_data, key) for key in SENSORS)


class KinderCloseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    # Datos detallados de menores: visibles en el estado actual, pero fuera de la base
    # de datos del historial (recorder); otras integraciones aún pueden acceder a ellos.
    _unrecorded_attributes = frozenset({"ficha", "consultado_en", "sesiones", "detalles", "elementos", "url_ficha"})

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        pupil_id = coordinator.entry.data[CONF_PUPIL_ID]
        self._attr_unique_id = f"{pupil_id}_{key}"
        self._attr_translation_key = key
        # Identificador fijo e independiente del idioma: es la interfaz documentada
        # para tarjetas y automatizaciones (docs/architecture.md).
        self.entity_id = f"sensor.kinderclose_{pupil_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, pupil_id)}, name=f"KinderClose {pupil_id}", manufacturer="KinderClose", entry_type=DeviceEntryType.SERVICE)
        if key == "ultima_ficha":
            self._attr_device_class = SensorDeviceClass.DATE
        elif key == "sueno":
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES

    @property
    def _record(self):
        """Ficha más reciente, o ``None`` si no hay ninguna en los últimos días."""
        return self.coordinator.data["ficha"]

    @property
    def native_value(self):
        record = self._record
        if record is None:
            return None
        if self.key == "ultima_ficha":
            return date.fromisoformat(record["fecha"])
        if self.key == "asistencia":
            return "ausente" if record["presencia"]["ausente"] else "presente"
        if self.key in ("entrada", "salida"):
            return record["presencia"]["hora_" + self.key]
        if self.key == "sueno":
            return record["sueno_minutos"]
        if self.key in ("deposiciones", "biberones", "recordatorios"):
            return len(record[self.key])
        return record["comidas"][self.key]

    @property
    def extra_state_attributes(self):
        record = self._record
        if record is None:
            attributes = {"fecha_ficha": None, "url_ficha": None}
            if self.key == "ultima_ficha":
                attributes["consultado_en"] = self.coordinator.data["consultado_en"]
            return attributes
        attributes = {"fecha_ficha": record["fecha"], "url_ficha": record["url"]}
        if self.key == "ultima_ficha":
            attributes.update(ficha=record, consultado_en=self.coordinator.data["consultado_en"])
        elif self.key == "asistencia":
            attributes["ausencia_justificada"] = record["presencia"]["ausencia_justificada"] if record["presencia"]["ausente"] else None
        elif self.key in ("entrada", "salida"):
            attributes[self.key + "_tarde"] = record["presencia"]["hora_" + self.key + "_tarde"]
        elif self.key == "sueno":
            attributes["sesiones"] = record["sueno"]
        elif self.key in ("deposiciones", "biberones"):
            attributes["detalles"] = record[self.key]
            if self.key == "deposiciones":
                attributes["control_esfinter"] = record["control_esfinter"]
        elif self.key == "recordatorios":
            attributes["elementos"] = record["recordatorios"]
        return attributes
