#!/usr/bin/env python3

import argparse
import asyncio
import ipaddress
import logging
import socket

# import sys
from pathlib import Path

import dns
import yaml
from aiorun import run
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
    DEFAULT_TELNET_TIMEOUT,
    EXTERNAL_DNS,
    VERSION,
)
from ha_mqtt_discoverable import Settings
from juicebox_mitm import JuiceboxMITM
from juicebox_mqtthandler import JuiceboxMQTTHandler
from juicebox_telnet import JuiceboxTelnet
from juicebox_udpcupdater import JuiceboxUDPCUpdater

AP_DESCRIPTION = """
JuicePass Proxy - by snicker
Publish JuiceBox data from a UDP Man in the Middle Proxy to MQTT discoverable by HomeAssistant.

https://github.com/snicker/juicepassproxy

To get the destination IP:Port of the EnelX server, telnet to your Juicenet device:

$ telnet 192.168.x.x 2000 and type the list command: list

! # Type  Info
# 0 FILE  webapp/index.html-1.4.0.24 (1995, 0)
# 1 UDPC  juicenet-udp-prod3-usa.enelx.com:8047 (26674)

The address is in the UDPC line.
Run ping, nslookup, or similar command to determine the IP.

As of November, 2023: juicenet-udp-prod3-usa.enelx.com = 54.161.185.130.
"""

logging.basicConfig(
    format="%(asctime)-20s %(levelname)-9s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/logs/juicepassproxy.log", mode="w"),
    ],
)
logger = logging.getLogger(__name__)


async def get_local_ip():
    # logger.debug(f"juicepassproxy Function: {sys._getframe().f_code.co_name}")
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        transport, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol,
            remote_addr=("10.254.254.254", 80),
            family=socket.AF_INET,
        )
        local_ip = transport.get_extra_info("sockname")[0]
    except Exception as e:
        logger.warning(f"Unable to get Local IP. ({e.__class__.__qualname__}: {e})")
        local_ip = None
    transport.close()
    return local_ip


async def resolve_ip_external_dns(address, use_dns=EXTERNAL_DNS):
    # logger.debug(f"juicepassproxy Function: {sys._getframe().f_code.co_name}")
    # res = await dns.asyncresolver.Resolver()
    res = dns.resolver.Resolver()
    res.nameservers = [use_dns]
    try:
        # answers = await res.resolve(
        answers = res.resolve(address, rdtype=dns.rdatatype.A, raise_on_no_answer=True)
    except (
        dns.resolver.LifetimeTimeout,
        dns.resolver.NoNameservers,
        dns.resolver.NoAnswer,
    ) as e:
        logger.warning(
            f"Unable to resolve {address}. ({e.__class__.__qualname__}: {e})"
        )
        return None

    if len(answers) > 0:
        return answers[0].address
    return None


async def is_valid_ip(test_ip):
    # logger.debug(f"juicepassproxy Function: {sys._getframe().f_code.co_name}")
    try:
        ipaddress.ip_address(test_ip)
    except ValueError:
        return False
    return True


async def get_enelx_server_port(juicebox_host, telnet_timeout=None):
    # logger.debug(f"juicepassproxy Function: {sys._getframe().f_code.co_name}")
    try:
        async with JuiceboxTelnet(
            juicebox_host,
            loglevel=logger.getEffectiveLevel(),
            timeout=telnet_timeout,
        ) as tn:
            connections = await tn.list()
            # logger.debug(f"connections: {connections}")
            for connection in connections:
                # logger.debug(f"connection['type']: {connection['type']}")
                # logger.debug(f"connection['dest']: {connection['dest']}")
                if connection["type"] == "UDPC" and not await is_valid_ip(
                    connection["dest"].split(":")[0]
                ):
                    return connection["dest"]
        return None
    # except Exception as e:
    #    logger.warning(
    #        f"Error in getting EnelX Server and Port via Telnet: ({
    #            e.__class__.__qualname__}) {e}"
    #    )
    #    return None
    finally:
        pass


async def get_juicebox_id(juicebox_host, telnet_timeout=None):
    # logger.debug(f"juicepassproxy Function: {sys._getframe().f_code.co_name}")
    try:
        async with JuiceboxTelnet(
            juicebox_host,
            loglevel=logger.getEffectiveLevel(),
            timeout=telnet_timeout,
        ) as tn:
            juicebox_id = (await tn.get_variable("email.name_address")).decode("utf-8")
            return juicebox_id
    # except Exception as e:
    #    logger.warning(
    #        f"Error in getting JuiceBox ID via Telnet: ({
    #            e.__class__.__qualname__}) {e}"
    #    )
    #    return None
    finally:
        pass


async def load_config(config_loc):
    # logger.debug(f"juicepassproxy Function: {sys._getframe().f_code.co_name}")
    config = {}
    try:
        with open(config_loc, "r") as file:
            config = yaml.safe_load(file)
    except Exception as e:
        logger.warning(f"Can't load {config_loc}. ({e.__class__.__qualname__}: {e})")
    if not config:
        config = {}
    return config


async def write_config(config, config_loc):
    # logger.debug(f"juicepassproxy Function: {sys._getframe().f_code.co_name}")
    try:
        with open(config_loc, "w") as file:
            yaml.dump(config, file)
        return True
    except Exception as e:
        logger.warning(
            f"Can't write to {config_loc}. ({e.__class__.__qualname__}: {e})"
        )
    return False


async def main():
    # logger.debug(f"juicepassproxy Function: {sys._getframe().f_code.co_name}")
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
    parser.add_argument(
        "--ignore_remote",
        action="store_true",
        help="If set, will not send received commands to the JuiceBox nor send outging local commands to EnelX",
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
        "--telnet_timeout",
        type=int,
        default=DEFAULT_TELNET_TIMEOUT,
        help="Timeout in seconds for Telnet operations (default: %(default)s)",
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

    parser.add_argument(
        "--experimental",
        action="store_true",
        help="<Need to explain what this does>",
    )

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    logger.info(f"Starting JuicePass Proxy {VERSION}")
    if args.update_udpc and not args.juicebox_host:
        raise argparse.ArgumentError(arg_juicebox_host, "juicebox_host is required")

    if not args.dst and not args.juicebox_host:
        raise argparse.ArgumentError(arg_juicebox_host, "juicebox_host is required")

    config_loc = Path(args.config_loc)
    config_loc.mkdir(parents=True, exist_ok=True)
    config_loc = config_loc.joinpath(CONF_YAML)
    config_loc.touch(exist_ok=True)
    logger.info(f"config_loc: {config_loc}")
    config = await load_config(config_loc)

    telnet_timeout = int(args.telnet_timeout)
    logging.debug(f"telnet timeout: {telnet_timeout}")
    if telnet_timeout == 0:
        telnet_timeout = None

    enelx_server_port = await get_enelx_server_port(
        args.juicebox_host, telnet_timeout=telnet_timeout
    )
    if enelx_server_port:
        logger.debug(f"enelx_server_port: {enelx_server_port}")
        enelx_server = enelx_server_port.split(":")[0]
        enelx_port = enelx_server_port.split(":")[1]
    else:
        enelx_server = config.get("ENELX_SERVER", DEFAULT_ENELX_SERVER)
        enelx_port = config.get("ENELX_PORT", DEFAULT_ENELX_PORT)
    config.update({"ENELX_SERVER": enelx_server})
    config.update({"ENELX_PORT": enelx_port})
    logger.info(f"enelx_server: {enelx_server}")
    logger.info(f"enelx_port: {enelx_port}")

    if args.src:
        if ":" in args.src:
            src = args.src
        else:
            src = f"{args.src}:{enelx_port}"
    elif local_ip := await get_local_ip():
        src = f"{local_ip}:{enelx_port}"
    else:
        src = f"{config.get('SRC', DEFAULT_SRC)}:{enelx_port}"
    config.update({"SRC": src.split(":")[0]})
    logger.info(f"src: {src}")

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
    elif enelx_server_ip := await resolve_ip_external_dns(enelx_server):
        dst = f"{enelx_server_ip}:{enelx_port}"
    else:
        dst = f"{config.get('DST', DEFAULT_DST)}:{enelx_port}"
    config.update({"DST": dst.split(":")[0]})
    logger.info(f"dst: {dst}")

    if juicebox_id := args.juicebox_id:
        pass
    elif juicebox_id := await get_juicebox_id(
        args.juicebox_host, telnet_timeout=telnet_timeout
    ):
        pass
    else:
        juicebox_id = config.get("JUICEBOX_ID")
    if juicebox_id:
        config.update({"JUICEBOX_ID": juicebox_id})
        logger.info(f"juicebox_id: {juicebox_id}")
    else:
        logger.error(
            "Cannot get JuiceBox ID from Telnet and not in Config. If a JuiceBox ID is later set or is obtained via Telnet, it will likely create a new JuiceBox Device with new Entities in Home Assistant."
        )

    if args.experimental:
        experimental = True
    else:
        experimental = False
    logger.info(f"experimental: {experimental}")

    if args.ignore_remote:
        ignore_remote = True
    else:
        ignore_remote = False
    logger.info(f"ignore_remote: {ignore_remote}")

    await write_config(config, config_loc)

    gather_list = []

    # try:
    #    loop = asyncio.get_running_loop()
    # except RuntimeError:
    #    loop = asyncio.new_event_loop()
    #    asyncio.set_event_loop(loop)

    mqtt_settings = Settings.MQTT(
        host=args.mqtt_host,
        port=args.mqtt_port,
        username=args.mqtt_user,
        password=args.mqtt_password,
        discovery_prefix=args.mqtt_discovery_prefix,
    )

    mqtt_handler = JuiceboxMQTTHandler(
        mqtt_settings=mqtt_settings,
        device_name=args.device_name,
        juicebox_id=juicebox_id,
        experimental=experimental,
        loglevel=logger.getEffectiveLevel(),
    )
    gather_list.append(asyncio.create_task(mqtt_handler.start()))

    mitm_handler = JuiceboxMITM(
        src,  # Local/Docker IP
        dst,  # EnelX IP
        ignore_remote=ignore_remote,
        loglevel=logger.getEffectiveLevel(),
    )
    await mitm_handler.set_local_data_handler(mqtt_handler.local_data_handler)
    await mitm_handler.set_remote_data_handler(mqtt_handler.remote_data_handler)
    gather_list.append(asyncio.create_task(mitm_handler.start()))

    await mqtt_handler.set_mitm_handler(mitm_handler)
    mitm_handler.mqtt_handler = mqtt_handler

    if args.update_udpc:
        address = src.split(":")
        jpp_host = args.juicepass_proxy_host or address[0]
        udpc_updater = JuiceboxUDPCUpdater(
            juicebox_host=args.juicebox_host,
            udpc_host=jpp_host,
            udpc_port=address[1],
            telnet_timeout=telnet_timeout,
            loglevel=logger.getEffectiveLevel(),
        )
        gather_list.append(asyncio.create_task(udpc_updater.start()))

    await asyncio.gather(
        *gather_list,
        return_exceptions=True,
    )

    # loop.close()
    logger.debug("juicepassproxy: end of main")


if __name__ == "__main__":
    run(main(), stop_on_unhandled_errors=True)
