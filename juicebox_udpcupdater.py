import asyncio
import logging

from juicebox_telnet import JuiceboxTelnet

_LOGGER = logging.getLogger(__name__)


class JuiceboxUDPCUpdater:
    def __init__(
        self,
        juicebox_host,
        jpp_host,
        udpc_port=8047,
        telnet_timeout=None,
        loglevel=None,
    ):
        if loglevel is not None:
            _LOGGER.setLevel(loglevel)
        self._juicebox_host = juicebox_host
        self._jpp_host = jpp_host
        self._udpc_port = udpc_port
        self._telnet_timeout = telnet_timeout
        self._default_loop_interval = 30
        self._run_udpc_update_loop = True
        self._udpc_update_loop_task = None
        self._telnet = None
        self._error_count = 0

    async def start(self):
        _LOGGER.info("Starting JuiceboxUDPCUpdater")

        await self._connect()

    async def _connect(self):
        _LOGGER.debug("JuiceboxUDPCUpdater _connect")

        if self._telnet is None:
            self._telnet = JuiceboxTelnet(
                self._juicebox_host,
                loglevel=_LOGGER.getEffectiveLevel(),
                timeout=self._telnet_timeout,
            )
            try:
                await self._telnet.open()
            except TimeoutError as e:
                self._error_count += 1
                _LOGGER.warning(
                    "JuiceboxUDPCUpdater Telnet Timeout. Reconnecting. "
                    f"({e.__class__.__qualname__}: {e}) (Errors: {self._error_count})"
                )
                self._telnet = None
                await self._connect()
                pass
            except ConnectionResetError as e:
                self._error_count += 1
                _LOGGER.warning(
                    "JuiceboxUDPCUpdater Telnet Connection Error. Reconnecting. "
                    f"({e.__class__.__qualname__}: {e}) (Errors: {self._error_count})"
                )
                await self._connect()
                pass
        if self._udpc_update_loop_task is None or self._udpc_update_loop_task.done():
            self._udpc_update_loop_task = await self._udpc_update_loop()
            self._loop.create_task(self._udpc_update_loop_task)
        _LOGGER.info("JuiceboxUDPCUpdater Connected to Juicebox Telnet")

    async def _udpc_update_loop(self):
        _LOGGER.debug("Starting JuiceboxUDPCUpdater Loop")
        while self._run_udpc_update_loop:
            loop_interval = self._default_loop_interval
            if self._telnet is None:
                self._error_count += 1
                _LOGGER.warning(
                    "JuiceboxUDPCUpdater Telnet Connection Lost. Reconnecting. (Errors: {self._error_count})"
                )
                await self._connect()
                continue
            loop_interval = await self._udpc_update_handler(loop_interval)
            await asyncio.sleep(loop_interval)

    async def _udpc_update_handler(self, default_loop_interval):
        loop_interval = default_loop_interval
        try:
            _LOGGER.info("JuiceboxUDPCUpdater Check Starting")
            connections = await self._telnet.get_udpc_list()
            update_required = True
            udpc_streams_to_close = {}  # Key = Connection id, Value = list id
            udpc_stream_to_update = 0

            # _LOGGER.debug(f"connections: {connections}")

            for i, connection in enumerate(connections):
                if connection["type"] == "UDPC":
                    udpc_streams_to_close.update({int(connection["id"]): i})
                    if self._jpp_host not in connection["dest"]:
                        udpc_stream_to_update = int(connection["id"])
            # _LOGGER.debug(f"udpc_streams_to_close: {udpc_streams_to_close}")
            if udpc_stream_to_update == 0 and len(udpc_streams_to_close) > 0:
                udpc_stream_to_update = int(max(udpc_streams_to_close, key=int))
            _LOGGER.debug(f"Active UDPC Stream: {udpc_stream_to_update}")

            for stream in list(udpc_streams_to_close):
                if stream < udpc_stream_to_update:
                    udpc_streams_to_close.pop(stream, None)

            if len(udpc_streams_to_close) == 0:
                _LOGGER.info("UDPC IP not found, updating")
            elif (
                self._jpp_host
                not in connections[udpc_streams_to_close[udpc_stream_to_update]]["dest"]
            ):
                _LOGGER.info("UDPC IP incorrect, updating")
            elif len(udpc_streams_to_close) == 1:
                _LOGGER.info("UDPC IP correct")
                update_required = False

            if update_required:
                for id in udpc_streams_to_close:
                    _LOGGER.debug(f"Closing UDPC stream: {id}")
                    await self._telnet.close_udpc_stream(id)
                await self._telnet.write_udpc_stream(self._jpp_host, self._udpc_port)
                await self._telnet.save_udpc()
                _LOGGER.info("UDPC IP Saved")
        except ConnectionResetError as e:
            self._error_count += 1
            _LOGGER.warning(
                "Telnet connection to JuiceBox lost. "
                "Nothing to worry about unless this happens a lot. "
                f"({e.__class__.__qualname__}: {e}) (Errors: {self._error_count})"
            )
            loop_interval = 3
        except TimeoutError as e:
            self._error_count += 1
            _LOGGER.warning(
                "Telnet connection to JuiceBox has timed out. "
                "Nothing to worry about unless this happens a lot. "
                f"({e.__class__.__qualname__}: {e}) (Errors: {self._error_count})"
            )
            loop_interval = 3
        except OSError as e:
            self._error_count += 1
            _LOGGER.warning(
                "Could not route Telnet connection to JuiceBox. "
                "Nothing to worry about unless this happens a lot. "
                f"({e.__class__.__qualname__}: {e}) (Errors: {self._error_count})"
            )
            loop_interval = 3
        # except Exception as e:
        #    _LOGGER.exception(f"Error in JuiceboxUDPCUpdater: ({e.__class__.__qualname__}: {e})")
        return loop_interval
