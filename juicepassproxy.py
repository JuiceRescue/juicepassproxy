#!/usr/bin/env python3

import argparse
import ipaddress
import logging
import socket
from pathlib import Path
from threading import Thread

import yaml
from const import (
    CONF_YAML,
    DEFAULT_DEVICE_NAME,
    DEFAULT_DST,
    DEFAULT_ENELX_PORT,
    DEFAULT_ENELX_SERVER,
    DEFAULT_MQTT_DISCOVERY_PREFIX,
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    DEFAULT_SRC,
    VERSION,
)
from dns import resolver
from ha_mqtt_discoverable import Settings
from juicebox_mqtthandler import JuiceboxMQTTHandler
from juicebox_telnet import JuiceboxTelnet
from juicepox_udpcupdater import JuiceboxUDPCUpdater
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


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(("10.254.254.254", 1))
        local_ip = s.getsockname()[0]
    except Exception as e:
        logging.warning(f"Unable to get local IP: {e}")
        local_ip = None
    s.close()
    return local_ip


def resolve_ip_external_dns(address, dns="1.1.1.1"):
    res = resolver.Resolver()
    res.nameservers = [dns]
    try:
        answers = res.resolve(address)
    except (
        resolver.LifetimeTimeout,
        resolver.NoNameservers,
        resolver.NoAnswer,
    ) as e:
        logging.warning(f"Unable to resolve {address}: {e}")
        return None

    if len(answers) > 0:
        return answers[0].address
    return None


def is_valid_ip(test_ip):
    try:
        ipaddress.ip_address(test_ip)
    except Exception:
        return False
    return True


def get_enelx_server_port(juicebox_host):
    try:
        with JuiceboxTelnet(juicebox_host) as tn:
            connections = tn.list()
            # logging.debug(f"connections: {connections}")
            for connection in connections:
                if connection["type"] == "UDPC" and not is_valid_ip(
                    connection["dest"].split(":")[0]
                ):
                    return connection["dest"]
        return None

    except Exception as e:
        logging.warning(f"Error in getting EnelX Server and Port via Telnet: {e}")
        return None


def get_juicebox_id(juicebox_host):
    try:
        with JuiceboxTelnet(juicebox_host) as tn:
            return (
                tn.get("email.name_address")
                .get("email.name_address")
                .replace("b'", "")
                .replace("'", "")
            )

        return None

    except Exception as e:
        logging.warning(f"Error in getting JuiceBox ID via Telnet: {e}")
        return None


def load_config(config_loc):
    config = {}
    try:
        with open(config_loc, "r") as file:
            config = yaml.safe_load(file)
    except Exception as e:
        logging.warning(f"Can't load {config_loc}: {e}")
    if not config:
        config = {}
    return config


def write_config(config, config_loc):
    try:
        with open(config_loc, "w") as file:
            yaml.dump(config, file)
        return True
    except Exception as e:
        logging.warning(f"Can't write to {config_loc}: {e}")
    return False


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=AP_DESCRIPTION
    )

    arg_src = parser.add_argument(
        "-s",
        "--src",
        required=False,
        type=str,
        help="Source IP (and optional port). If not defined, will obtain it automatically. (Ex. 127.0.0.1:8047)",
    )
    parser.add_argument(
        "-d",
        "--dst",
        required=False,
        type=str,
        help="Destination IP (and optional port) of EnelX Server. If not defined, --juicebox_host required and then will obtain it automatically. (Ex. 127.0.0.1:8047)",
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("-u", "--mqtt_user", type=str, help="MQTT Username")
    parser.add_argument("-P", "--mqtt_password", type=str, help="MQTT Password")
    parser.add_argument(
        "-H",
        "--mqtt_host",
        type=str,
        default=DEFAULT_MQTT_HOST,
        help="MQTT Hostname to connect to (default: %(default)s)",
    )
    parser.add_argument(
        "-p",
        "--mqtt_port",
        type=int,
        default=DEFAULT_MQTT_PORT,
        help="MQTT Port (default: %(default)s)",
    )
    parser.add_argument(
        "-D",
        "--mqtt_discovery_prefix",
        type=str,
        dest="mqtt_discovery_prefix",
        default=DEFAULT_MQTT_DISCOVERY_PREFIX,
        help="Home Assistant MQTT topic prefix (default: %(default)s)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=DEFAULT_DEVICE_NAME,
        help="Home Assistant Device Name (default: %(default)s)",
        dest="device_name",
    )
    parser.add_argument(
        "--juicebox_id",
        type=str,
        help="JuiceBox ID. If not defined, will obtain it automatically.",
        dest="juicebox_id",
    )
    parser.add_argument(
        "--update_udpc",
        action="store_true",
        help="Update UDPC on the JuiceBox. Requires --juicebox_host",
    )
    parser.add_argument(
        "--udpc_timeout",
        type=int,
        default=0,
        help="Timeout setting for UDPC Updater",
    )
    arg_juicebox_host = parser.add_argument(
        "--juicebox_host",
        type=str,
        help="Host or IP address of the JuiceBox. Required for --update_udpc or if --dst not defined.",
    )
    parser.add_argument(
        "--juicepass_proxy_host",
        type=str,
        help="EXTERNAL host or IP address of the machine running JuicePass"
        " Proxy. Optional: only necessary when using --update_udpc and"
        " it will be inferred from the address in --src if omitted.",
    )
    parser.add_argument(
        "--config_loc",
        type=str,
        default=Path.home().joinpath(".juicepassproxy"),
        help="The location to store the config file  (default: %(default)s)",
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    logging.info(f"Starting JuicePass Proxy {VERSION}")
    if args.update_udpc and not args.juicebox_host:
        raise argparse.ArgumentError(arg_juicebox_host, "juicebox_host is required")

    if not args.dst and not args.juicebox_host:
        raise argparse.ArgumentError(arg_juicebox_host, "juicebox_host is required")

    config_loc = Path(args.config_loc)
    config_loc.mkdir(parents=True, exist_ok=True)
    config_loc = config_loc.joinpath(CONF_YAML)
    config_loc.touch(exist_ok=True)
    logging.info(f"config_loc: {config_loc}")
    config = load_config(config_loc)

    if enelx_server_port := get_enelx_server_port(args.juicebox_host):
        logging.debug(f"enelx_server_port: {enelx_server_port}")
        enelx_server = enelx_server_port.split(":")[0]
        enelx_port = enelx_server_port.split(":")[1]
    else:
        enelx_server = config.get("ENELX_SERVER", DEFAULT_ENELX_SERVER)
        enelx_port = config.get("ENELX_PORT", DEFAULT_ENELX_PORT)
    config.update({"ENELX_SERVER": enelx_server})
    config.update({"ENELX_PORT": enelx_port})
    logging.info(f"enelx_server: {enelx_server}")
    logging.info(f"enelx_port: {enelx_port}")

    if args.src:
        if ":" in args.src:
            src = args.src
        else:
            src = f"{args.src}:{enelx_port}"
    elif local_ip := get_local_ip():
        src = f"{local_ip}:{enelx_port}"
    else:
        src = f"{config.get('SRC', DEFAULT_SRC)}:{enelx_port}"
    config.update({"SRC": src.split(":")[0]})
    logging.info(f"src: {src}")

    localhost_src = src.startswith("0.") or src.startswith("127")
    if args.update_udpc and localhost_src and not args.juicepass_proxy_host:
        raise argparse.ArgumentError(
            arg_src,
            "src must not be a local IP address for update_udpc to work, or"
            " --juicepass_proxy_host must be used.",
        )

    if args.dst:
        if ":" in args.dst:
            dst = args.dst
        else:
            dst = f"{args.dst}:{enelx_port}"
    elif enelx_server_ip := resolve_ip_external_dns(enelx_server):
        dst = f"{enelx_server_ip}:{enelx_port}"
    else:
        dst = f"{config.get('DST', DEFAULT_DST)}:{enelx_port}"
    config.update({"DST": dst.split(":")[0]})
    logging.info(f"dst: {dst}")

    if juicebox_id := args.juicebox_id:
        pass
    elif juicebox_id := get_juicebox_id(args.juicebox_host):
        pass
    else:
        juicebox_id = config.get("JUICEBOX_ID")
    if juicebox_id:
        config.update({"JUICEBOX_ID": juicebox_id})
        logging.info(f"juicebox_id: {juicebox_id}")
    else:
        logging.error(
            "Cannot get JuiceBox ID from Telnet and not in Config. If a JuiceBox ID is later set or is obtained via Telnet, it will likely create a new JuiceBox Device with new Entities in Home Assistant."
        )
    write_config(config, config_loc)

    mqttsettings = Settings.MQTT(
        host=args.mqtt_host,
        port=args.mqtt_port,
        username=args.mqtt_user,
        password=args.mqtt_password,
        discovery_prefix=args.mqtt_discovery_prefix,
    )
    handler = JuiceboxMQTTHandler(
        mqtt_settings=mqttsettings,
        device_name=args.device_name,
        juicebox_id=juicebox_id,
    )
    handler.basic_message_publish(
        {"type": "debug", "debug_message": f"INFO: Starting JuicePass Proxy {VERSION}"}
    )
    pyproxy.LOCAL_DATA_HANDLER = handler.local_data_handler
    pyproxy.REMOTE_DATA_HANDLER = handler.remote_data_handler

    udpc_updater_thread = None
    udpc_updater = None

    if args.update_udpc:
        address = src.split(":")
        jpp_host = args.juicepass_proxy_host or address[0]
        udpc_timeout = int(args.udpc_timeout)
        logging.debug(f"udpc timeout: {udpc_timeout}")
        if udpc_timeout == 0:
            udpc_timeout = None
        udpc_updater = JuiceboxUDPCUpdater(
            args.juicebox_host, jpp_host, address[1], udpc_timeout
        )
        udpc_updater_thread = Thread(target=udpc_updater.start)
        udpc_updater_thread.start()

    pyproxy.udp_proxy(src, dst)

    if udpc_updater is not None and udpc_updater_thread is not None:
        udpc_updater.run_event = False
        udpc_updater_thread.join()


if __name__ == "__main__":
    main()
