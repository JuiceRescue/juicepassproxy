import logging
import re

from const import VERSION
from ha_mqtt_discoverable import DeviceInfo, Settings
from ha_mqtt_discoverable.sensors import Sensor, SensorInfo


class JuiceboxMQTTHandler:
    def __init__(self, device_name, mqtt_settings, juicebox_id=None):
        self.mqtt_settings = mqtt_settings
        self.device_name = device_name
        self.juicebox_id = juicebox_id
        self.entities = {
            "status": None,
            "current": None,
            "frequency": None,
            "energy_lifetime": None,
            "energy_session": None,
            "temperature": None,
            "voltage": None,
            "power": None,
            "debug_message": None,
        }
        self._init_devices()

    def _init_devices(self):
        device_info = DeviceInfo(
            name=self.device_name,
            identifiers=(
                [self.juicebox_id]
                if self.juicebox_id is not None
                else [self.device_name]
            ),
            connections=[
                (
                    ["JuiceBox ID", self.juicebox_id]
                    if self.juicebox_id is not None
                    else []
                )
            ],
            manufacturer="EnelX",
            model="JuiceBox",
            sw_version=VERSION,
            via_device="JuicePass Proxy",
        )
        self._init_device_status(device_info)
        self._init_device_current(device_info)
        self._init_device_frequency(device_info)
        self._init_device_energy_lifetime(device_info)
        self._init_device_energy_session(device_info)
        self._init_device_temperature(device_info)
        self._init_device_voltage(device_info)
        self._init_device_power(device_info)
        self._init_debug_message(device_info)

    def _init_device_status(self, device_info):
        name = "Status"
        sensor_info = SensorInfo(
            name=name,
            unique_id=f"{self.juicebox_id} {name}",
            icon="mdi:ev-station",
            device=device_info,
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities["status"] = sensor

    def _init_debug_message(self, device_info):
        name = "Last Debug Message"
        sensor_info = SensorInfo(
            name=name,
            unique_id=f"{self.juicebox_id} {name}",
            expire_after=60,
            enabled_by_default=False,
            icon="mdi:bug",
            entity_category="diagnostic",
            device=device_info,
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities["debug_message"] = sensor

    def _init_device_current(self, device_info):
        name = "Current"
        sensor_info = SensorInfo(
            name=name,
            unique_id=f"{self.juicebox_id} {name}",
            state_class="measurement",
            device_class="current",
            unit_of_measurement="A",
            device=device_info,
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities["current"] = sensor

    def _init_device_frequency(self, device_info):
        name = "Frequency"
        sensor_info = SensorInfo(
            name=name,
            unique_id=f"{self.juicebox_id} {name}",
            state_class="measurement",
            device_class="frequency",
            unit_of_measurement="Hz",
            device=device_info,
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities["frequency"] = sensor

    def _init_device_energy_lifetime(self, device_info):
        name = "Energy (Lifetime)"
        sensor_info = SensorInfo(
            name=name,
            unique_id=f"{self.juicebox_id} {name}",
            state_class="total_increasing",
            device_class="energy",
            unit_of_measurement="Wh",
            device=device_info,
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities["energy_lifetime"] = sensor

    def _init_device_energy_session(self, device_info):
        name = "Energy (Session)"
        sensor_info = SensorInfo(
            name=name,
            unique_id=f"{self.juicebox_id} {name}",
            state_class="total_increasing",
            device_class="energy",
            unit_of_measurement="Wh",
            device=device_info,
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities["energy_session"] = sensor

    def _init_device_temperature(self, device_info):
        name = "Temperature"
        sensor_info = SensorInfo(
            name=name,
            unique_id=f"{self.juicebox_id} {name}",
            state_class="measurement",
            device_class="temperature",
            unit_of_measurement="°F",
            device=device_info,
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities["temperature"] = sensor

    def _init_device_voltage(self, device_info):
        name = "Voltage"
        sensor_info = SensorInfo(
            name=name,
            unique_id=f"{self.juicebox_id} {name}",
            state_class="measurement",
            device_class="voltage",
            unit_of_measurement="V",
            device=device_info,
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities["voltage"] = sensor

    def _init_device_power(self, device_info):
        name = "Power"
        sensor_info = SensorInfo(
            name=name,
            unique_id=f"{self.juicebox_id} {name}",
            state_class="measurement",
            device_class="power",
            unit_of_measurement="W",
            device=device_info,
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities["power"] = sensor

    def basic_message_try_parse(self, data):
        message = {"type": "basic"}
        message["current"] = 0
        message["energy_session"] = 0
        active = True
        parts = re.split(r",|!|:", str(data).replace("b'", "").replace("'", ""))
        parts.pop(0)  # JuiceBox ID
        parts.pop(-1)  # Ending blank
        parts.pop(-1)  # Checksum

        # Undefined parts: v, F, u, M, C, m, t, i, e, r, b, B, P, p
        # s = Counter
        for part in parts:
            if part[0] == "S":
                message["status"] = {
                    "S0": "Unplugged",
                    "S1": "Plugged In",
                    "S2": "Charging",
                    "S5": "Error",
                    "S00": "Unplugged",
                    "S01": "Plugged In",
                    "S02": "Charging",
                    "S05": "Error",
                }.get(part)
                if message["status"] is None:
                    message["status"] = "unknown {}".format(part)
                active = message["status"].lower() == "charging"
            elif part[0] == "A" and active:
                message["current"] = round(float(part.split("A")[1]) * 0.1, 2)
            elif part[0] == "f":
                message["frequency"] = round(float(part.split("f")[1]) * 0.01, 2)
            elif part[0] == "L":
                message["energy_lifetime"] = float(part.split("L")[1])
            elif part[0] == "E" and active:
                message["energy_session"] = float(part.split("E")[1])
            elif part[0] == "T":
                message["temperature"] = round(float(part.split("T")[1]) * 1.8 + 32, 2)
            elif part[0] == "V":
                message["voltage"] = round(float(part.split("V")[1]) * 0.1, 2)
        message["power"] = round(
            message.get("voltage", 0) * message.get("current", 0), 2
        )
        return message

    def pyproxy_oserror_message_try_parse(self, data):
        message = {"type": "pyproxy_oserror"}
        err_data = str(data).split("|")
        message["status"] = "unavailable"
        message["debug_message"] = (
            f"PyProxy {err_data[1].title()} OSError {err_data[3]} [{
                err_data[2]}]: {err_data[4]}"
        )
        return message

    def debug_message_try_parse(self, data):
        message = {"type": "debug"}
        dbg_data = (
            str(data)
            .replace("https://", "https//")
            .replace("http://", "http//")
            .split(":")
        )
        dbg_level_abbr = dbg_data[1].split(",")[1]
        if dbg_level_abbr == "NFO":
            dbg_level = "INFO"
        elif dbg_level_abbr == "WRN":
            dbg_level = "WARNING"
        elif dbg_level_abbr == "ERR":
            dbg_level = "ERROR"
        else:
            dbg_level = dbg_level_abbr
        dbg_msg = (
            dbg_data[2].replace("https//", "https://").replace("http//", "http://")
        )
        message["debug_message"] = f"{dbg_level}: {dbg_msg}"
        return message

    def basic_message_publish(self, message):
        logging.debug(f"{message.get('type')} message: {message}")
        try:
            for k in message:
                entity = self.entities.get(k)
                if entity:
                    entity.set_state(message.get(k))
        except Exception as e:
            logging.exception(f"Failed to publish sensor data to MQTT: {e}")

    def remote_data_handler(self, data):
        try:
            logging.debug("remote: {}".format(data))
            return data
        except IndexError as e:
            logging.warning(
                "Index error when handling remote data, probably wrong number of items in list"
                f"- nothing to worry about unless this happens a lot. ({e})"
            )
        except Exception as e:
            logging.exception(f"Exception handling local data: {e}")

    def local_data_handler(self, data):
        try:
            logging.debug("local: {}".format(data))
            if "PYPROXY_OSERROR" in str(data):
                message = self.pyproxy_oserror_message_try_parse(data)
            elif ":DBG," in str(data):
                message = self.debug_message_try_parse(data)
            else:
                message = self.basic_message_try_parse(data)
            if message:
                self.basic_message_publish(message)
            return data
        except IndexError as e:
            logging.warning(
                "Index error when handling local data, probably wrong number of items in list"
                f"- nothing to worry about unless this happens a lot. ({e})"
            )
        except Exception as e:
            logging.exception(f"Exception handling local data: {e}")
