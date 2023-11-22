import argparse
import logging
import time
from threading import Thread

from ha_mqtt_discoverable import DeviceInfo, Settings
from ha_mqtt_discoverable.sensors import Sensor, SensorInfo
from juicebox_telnet import JuiceboxTelnet
from pyproxy import pyproxy

AP_DESCRIPTION = """
JuicePass Proxy - by snicker
publish JuiceBox data from a UDP proxy to MQTT discoverable by HomeAssistant.
hopefully we won't need this if EnelX fixes their API!
https://github.com/home-assistant/core/issues/86588

To get the destination IP:Port of the EnelX server, telnet to your Juicenet
device:
$ telnet 192.168.x.x 2000
and give a `list` command:
> list
> ! # Type  Info
> # 0 FILE  webapp/index.html-1.4.0.24 (1995, 0)
> # 1 UDPC  juicenet-udp-prod3-usa.enelx.com:8047 (26674)
the address is in the UDPC line- give that an nslookup or other to determine IP
juicenet-udp-prod3-usa.enelx.com - 54.161.185.130

this may change over time- but if you are using a local DNS server to reroute
those requests to this proxy, you should stick to using the IP address here to
avoid nameserver lookup loops.
"""


class JuiceboxMessageHandler(object):
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
        }
        self._init_devices()

    def _init_devices(self):
        device_info = DeviceInfo(
            name=self.device_name,
            identifiers=[self.juicebox_id]
            if self.juicebox_id is not None
            else [self.device_name],
            connections=[
                ["JuiceBox ID", self.juicebox_id]
                if self.juicebox_id is not None
                else []
            ],
            manufacturer="EnelX",
            model="JuiceBox",
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

    def _init_device_status(self, device_info):
        name = "Status"
        sensor_info = SensorInfo(
            name=name, unique_id=f"{self.juicebox_id} {name}", device=device_info
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities["status"] = sensor

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
        for part in str(data).split(","):
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
        logging.debug(f"message: {message}")
        return message

    def basic_message_publish(self, message):
        logging.debug("basic message {}".format(message))
        try:
            for k in message:
                entity = self.entities.get(k)
                if entity:
                    entity.set_state(message.get(k))
        except Exception as e:
            logging.exception(f"failed to publish sensor data: {e}")

    def remote_data_handler(self, data):
        logging.debug("remote: {}".format(data))
        return data

    def local_data_handler(self, data):
        logging.debug("local : {}".format(data))
        message = self.basic_message_try_parse(data)
        if message:
            self.basic_message_publish(message)
        return data


class JuiceboxUDPCUpdater(object):
    def __init__(self, juicebox_host, udpc_host, udpc_port=8047):
        self.juicebox_host = juicebox_host
        self.udpc_host = udpc_host
        self.udpc_port = udpc_port
        self.interval = 30
        self.run_event = True

    def start(self):
        while self.run_event:
            interval = self.interval
            try:
                logging.debug("JuiceboxUDPCUpdater check...")
                with JuiceboxTelnet(self.juicebox_host, 2000) as tn:
                    connections = tn.list()
                    update_required = True
                    udpc_streams_to_close = {}  # Key = Connection id, Value = list id
                    udpc_stream_to_update = 0

                    # logging.debug(f"connections: {connections}")

                    for i, connection in enumerate(connections):
                        if connection["type"] == "UDPC":
                            udpc_streams_to_close.update({int(connection["id"]): i})
                            if self.udpc_host not in connection["dest"]:
                                udpc_stream_to_update = int(connection["id"])
                    # logging.debug(f"udpc_streams_to_close: {udpc_streams_to_close}")
                    if udpc_stream_to_update == 0 and len(udpc_streams_to_close) > 0:
                        udpc_stream_to_update = int(max(udpc_streams_to_close, key=int))
                    logging.debug(f"Active UDPC Stream: {udpc_stream_to_update}")

                    for stream in list(udpc_streams_to_close):
                        if stream < udpc_stream_to_update:
                            udpc_streams_to_close.pop(stream, None)

                    if len(udpc_streams_to_close) == 0:
                        logging.info("UDPC IP not found, updating...")
                    elif (
                        self.udpc_host
                        not in connections[
                            udpc_streams_to_close[udpc_stream_to_update]
                        ]["dest"]
                    ):
                        logging.info("UDPC IP incorrect, updating...")
                    elif len(udpc_streams_to_close) == 1:
                        logging.info("UDPC IP correct")
                        update_required = False

                    if update_required:
                        for id in udpc_streams_to_close:
                            logging.debug(f"Closing UDPC stream: {id}")
                            tn.stream_close(id)
                        tn.udpc(self.udpc_host, self.udpc_port)
                        tn.save()
                        logging.info("UDPC IP Saved")
            except ConnectionResetError as e:
                logging.warning(
                    "Telnet connection to JuiceBox lost- nothing to worry"
                    f" about unless this happens a lot. Retrying in 3s. ({e})"
                )
                interval = 3
            except Exception as e:
                logging.exception(f"Error in JuiceboxUDPCUpdater: {e}")
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=AP_DESCRIPTION
    )

    arg_src = parser.add_argument(
        "-s",
        "--src",
        required=True,
        default="127.0.0.1:8047",
        help="Source IP and port, (default: %(default)s)",
    )
    parser.add_argument(
        "-d", "--dst", required=True, help="Destination IP and port of EnelX Server."
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("-u", "--user", type=str, help="MQTT username")
    parser.add_argument("-P", "--password", type=str, help="MQTT password")
    parser.add_argument(
        "-H",
        "--host",
        type=str,
        default="127.0.0.1",
        help="MQTT hostname to connect to (default: %(default)s)",
    )
    parser.add_argument(
        "-p", "--port", type=int, default=1883, help="MQTT port (default: %(default)s)"
    )
    parser.add_argument(
        "-D",
        "--discovery-prefix",
        type=str,
        dest="discovery_prefix",
        default="homeassistant",
        help="Home Assistant MQTT topic prefix (default: %(default)s)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="Juicebox",
        help="Home Assistant Device Name (default: %(default)s)",
        dest="device_name",
    )
    parser.add_argument(
        "--juicebox_id", type=str, help="JuiceBox ID", dest="juicebox_id"
    )
    parser.add_argument(
        "--update_udpc",
        action="store_true",
        help="Update UDPC on the JuiceBox. Requires --juicebox_host",
    )
    arg_juicebox_host = parser.add_argument(
        "--juicebox_host",
        type=str,
        help="Host or IP address of the JuiceBox. required for --update_udpc",
    )
    parser.add_argument(
        "--juicepass_proxy_host",
        type=str,
        help="EXTERNAL host or IP address of the machine running JuicePass"
        " Proxy. Optional: only necessary when using --update_udpc and"
        " it will be inferred from the address in --src if omitted.",
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.update_udpc and not args.juicebox_host:
        raise argparse.ArgumentError(arg_juicebox_host, "juicebox_host is required")

    localhost_src = args.src.startswith("0.") or args.src.startswith("127")
    if args.update_udpc and localhost_src and not args.juicepass_proxy_host:
        raise argparse.ArgumentError(
            arg_src,
            "src must not be a local IP address for update_udpc to work, or"
            " --juicepass_proxy_host must be used.",
        )

    mqttsettings = Settings.MQTT(
        host=args.host,
        port=args.port,
        username=args.user,
        password=args.password,
        discovery_prefix=args.discovery_prefix,
    )
    handler = JuiceboxMessageHandler(
        mqtt_settings=mqttsettings,
        device_name=args.device_name,
        juicebox_id=args.juicebox_id,
    )

    pyproxy.LOCAL_DATA_HANDLER = handler.local_data_handler
    pyproxy.REMOTE_DATA_HANDLER = handler.remote_data_handler

    udpc_updater_thread = None
    udpc_updater = None

    if args.update_udpc:
        address = args.src.split(":")
        jpp_host = args.juicepass_proxy_host or address[0]
        udpc_updater = JuiceboxUDPCUpdater(args.juicebox_host, jpp_host, address[1])
        udpc_updater_thread = Thread(target=udpc_updater.start)
        udpc_updater_thread.start()

    pyproxy.udp_proxy(args.src, args.dst)

    if udpc_updater is not None and udpc_updater_thread is not None:
        udpc_updater.run_event = False
        udpc_updater_thread.join()


if __name__ == "__main__":
    main()
