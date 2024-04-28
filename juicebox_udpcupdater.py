import logging
import time

from juicebox_telnet import JuiceboxTelnet

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


class JuiceboxUDPCUpdater(object):
    def __init__(self, juicebox_host, udpc_host, udpc_port=8047, timeout=None):
        self.juicebox_host = juicebox_host
        self.udpc_host = udpc_host
        self.udpc_port = udpc_port
        self.interval = 30
        self.run_event = True
        self.timeout = timeout

    def start(self):
        while self.run_event:
            interval = self.interval
            try:
                logging.debug("JuiceboxUDPCUpdater check... ")
                with JuiceboxTelnet(self.juicebox_host, 2000, self.timeout) as tn:
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
                    "Telnet connection to JuiceBox lost"
                    f"- nothing to worry about unless this happens a lot. Retrying in 3s. ({
                        e})"
                )
                interval = 3
            except TimeoutError as e:
                logging.warning(
                    "Telnet connection to JuiceBox has timed out"
                    f"- nothing to worry about unless this happens a lot. Retrying in 3s. ({
                        e})"
                )
                interval = 3
            except OSError as e:
                logging.warning(
                    "Could not route Telnet connection to JuiceBox"
                    f"- nothing to worry about unless this happens a lot. Retrying in 3s. ({
                        e})"
                )
                interval = 3
            except Exception as e:
                logging.exception(f"Error in JuiceboxUDPCUpdater: {e}")
            time.sleep(interval)
