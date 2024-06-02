import asyncio
import errno
import logging
import time

import asyncio_dgram
from const import (
    ERROR_LOOKBACK_MIN,
    MAX_ERROR_COUNT,
    MAX_RETRY_ATTEMPT,
    MITM_HANDLER_TIMEOUT,
    MITM_RECV_TIMEOUT,
    MITM_SEND_DATA_TIMEOUT,
)
from juicebox_message import JuiceboxMessage, JuiceboxCommand

# Began with https://github.com/rsc-dev/pyproxy and rewrote when moving to async.

_LOGGER = logging.getLogger(__name__)


class JuiceboxMITM:

    def __init__(
        self,
        jpp_addr,
        enelx_addr,
        local_mitm_handler=None,
        ignore_enelx=False,
        remote_mitm_handler=None,
        mqtt_handler=None,
        loglevel=None,
    ):
        if loglevel is not None:
            _LOGGER.setLevel(loglevel)
        self._jpp_addr = jpp_addr
        self._enelx_addr = enelx_addr
        self._juicebox_addr = None
        self._ignore_enelx = ignore_enelx
        self._local_mitm_handler = local_mitm_handler
        self._remote_mitm_handler = remote_mitm_handler
        self._mqtt_handler = mqtt_handler
        self._loop = asyncio.get_running_loop()
        self._mitm_loop_task: asyncio.Task = None
        self._sending_lock = asyncio.Lock()
        self._dgram = None
        self._error_count = 0
        self._error_timestamp_list = []
        # Last command sent to juicebox device
        self._last_command = None
        # Last message received from juicebox device
        self._last_message = None

    async def start(self) -> None:
        _LOGGER.info("Starting JuiceboxMITM")
        _LOGGER.debug(f"JPP: {self._jpp_addr[0]}:{self._jpp_addr[1]}")
        _LOGGER.debug(f"EnelX: {self._enelx_addr[0]}:{self._enelx_addr[1]}")

        await self._connect()

    async def close(self):
        if self._dgram is not None:
            self._dgram.close()
            self._dgram = None
            await asyncio.sleep(3)

    async def _connect(self):
        connect_attempt = 1
        while (
            self._dgram is None
            and connect_attempt <= MAX_RETRY_ATTEMPT
            and self._error_count < MAX_ERROR_COUNT
        ):
            if connect_attempt != 1:
                _LOGGER.debug(
                    "Retrying UDP Server Startup. Attempt "
                    f"{connect_attempt} of {MAX_RETRY_ATTEMPT}"
                )
            connect_attempt += 1
            try:
                if self._sending_lock.locked():
                    self._dgram = await asyncio_dgram.bind(
                        self._jpp_addr, reuse_port=True
                    )
                else:
                    async with self._sending_lock:
                        self._dgram = await asyncio_dgram.bind(
                            self._jpp_addr, reuse_port=True
                        )
            except OSError as e:
                _LOGGER.warning(
                    "JuiceboxMITM UDP Server Startup Error. Reconnecting. "
                    f"({e.__class__.__qualname__}: {e})"
                )
                await self._add_error()
                self._dgram = None
                pass
            await asyncio.sleep(5)
        if self._dgram is None:
            raise ChildProcessError("JuiceboxMITM: Unable to start MITM UDP Server.")
        if self._mitm_loop_task is None or self._mitm_loop_task.done():
            self._mitm_loop_task = await self._mitm_loop()
            self._loop.create_task(self._mitm_loop_task)
        _LOGGER.debug(f"JuiceboxMITM Connected. {self._jpp_addr}")

    async def _mitm_loop(self) -> None:
        _LOGGER.debug("Starting JuiceboxMITM Loop")
        while self._error_count < MAX_ERROR_COUNT:
            if self._dgram is None:
                _LOGGER.warning("JuiceboxMITM Reconnecting.")
                await self._add_error()
                await self._connect()
                continue
            # _LOGGER.debug("Listening")
            try:
                async with asyncio.timeout(MITM_RECV_TIMEOUT):
                    data, remote_addr = await self._dgram.recv()
            except asyncio_dgram.TransportClosed:
                _LOGGER.warning("JuiceboxMITM Connection Lost.")
                await self._add_error()
                self._dgram = None
                continue
            except TimeoutError as e:
                _LOGGER.warning(
                    f"No Message Received after {MITM_RECV_TIMEOUT} sec. "
                    f"({e.__class__.__qualname__}: {e})"
                )
                await self._add_error()
                self._dgram = None
                continue
            try:
                async with asyncio.timeout(MITM_HANDLER_TIMEOUT):
                    await self._main_mitm_handler(data, remote_addr)
            except TimeoutError as e:
                _LOGGER.warning(
                    f"MITM Handler timeout after {MITM_HANDLER_TIMEOUT} sec. "
                    f"({e.__class__.__qualname__}: {e})"
                )
                await self._add_error()
                self._dgram = None
        raise ChildProcessError(
            f"JuiceboxMITM: More than {self._error_count} errors in the last "
            f"{ERROR_LOOKBACK_MIN} min."
        )

    async def _main_mitm_handler(self, data: bytes, from_addr: tuple[str, int]):
        if data is None or from_addr is None:
            return

        # _LOGGER.debug(f"JuiceboxMITM Recv: {data} from {from_addr}")
        if from_addr[0] != self._enelx_addr[0]:
            self._juicebox_addr = from_addr

        if from_addr == self._juicebox_addr:
            # Must decode message to give correct command response based on version
            # Also this decoded message can be passed to the mqtt handler to skip a new decoding
            try:
                self._last_message = JuiceboxMessage().from_string(data.decode("utf-8"))
            except Exception as e:
                _LOGGER.exception(f"Not a valid juicebox message {data}")

            data = await self._local_mitm_handler(data)

            if self._ignore_enelx:
                # Keep sending responses to local juicebox like the enelx servers using last values
                await self.send_cmd_message_to_juicebox(new_values=False)
            else:
                try:
                    await self.send_data(data, self._enelx_addr)
                except OSError as e:
                    _LOGGER.warning(
                        f"JuiceboxMITM OSError {errno.errorcode[e.errno]} "
                        f"[{self._enelx_addr}]: {e}"
                    )
                    await self._local_mitm_handler(
                        f"JuiceboxMITM_OSERROR|server|{self._enelx_addr}|"
                        f"{errno.errorcode[e.errno]}|{e}"
                    )
                    await self._add_error()
        elif self._juicebox_addr is not None and from_addr == self._enelx_addr:
            if not self._ignore_enelx:
                data = await self._remote_mitm_handler(data)
                try:
                    await self.send_data(data, self._juicebox_addr)
                except OSError as e:
                    _LOGGER.warning(
                        f"JuiceboxMITM OSError {errno.errorcode[e.errno]} "
                        f"[{self._juicebox_addr}]: {e}"
                    )
                    await self._local_mitm_handler(
                        f"JuiceboxMITM_OSERROR|client|{self._juicebox_addr}|"
                        f"{errno.errorcode[e.errno]}|{e}"
                    )
                    await self._add_error()
            else:
                _LOGGER.info(f"JuiceboxMITM Ignoring From EnelX: {data}")
        else:
            _LOGGER.warning(f"JuiceboxMITM Unknown address: {from_addr}")

    async def send_data(
        self, data: bytes, to_addr: tuple[str, int], blocking_time: int = 0.1
    ):
        sent = False
        send_attempt = 1
        while not sent and send_attempt <= MAX_RETRY_ATTEMPT:
            if send_attempt != 1:
                _LOGGER.warning(
                    f"JuiceboxMITM Resending (Attempt: {send_attempt} of "
                    f"{MAX_RETRY_ATTEMPT}): {data} to {to_addr}"
                )
            send_attempt += 1

            if self._dgram is None:
                _LOGGER.warning("JuiceboxMITM Reconnecting.")
                await self._connect()

            try:
                async with asyncio.timeout(MITM_SEND_DATA_TIMEOUT):
                    async with self._sending_lock:
                        try:
                            await self._dgram.send(data, to_addr)
                        except asyncio_dgram.TransportClosed:
                            _LOGGER.warning(
                                "JuiceboxMITM Connection Lost while Sending."
                            )
                            await self._add_error()
                            self._dgram = None
                        else:
                            sent = True
            except TimeoutError as e:
                _LOGGER.warning(
                    f"Send Data timeout after {MITM_SEND_DATA_TIMEOUT} sec. "
                    f"({e.__class__.__qualname__}: {e})"
                )
                await self._add_error()
            await asyncio.sleep(max(blocking_time, 0.1))
        if not sent:
            raise ChildProcessError("JuiceboxMITM: Unable to send data.")

        # _LOGGER.debug(f"JuiceboxMITM Sent: {data} to {to_addr}")

    async def send_data_to_juicebox(self, data: bytes):
        await self.send_data(data, self._juicebox_addr)


    def is_mqtt_entity_defined(self, entity_name):
        return self._mqtt_handler.get_entity(entity_name) and self._mqtt_handler.get_entity(entity_name).state
        
    def __build_cmd_message(self, new_values):
       
       # TODO: check which other versions can be considered as new_version of protocol
       new_version = self._last_message and (self._last_message.get_value("v") == "09u")
       if self._last_command:
          message = JuiceboxCommand(previous=self._last_command, new_version=new_version)
       else:
          message = JuiceboxCommand(new_version=new_version)
          # Must start with values 
          new_values = True
          
       if new_values:
           message.offline_amperage = int(self._mqtt_handler.get_entity("current_max").state)
           message.instant_amperage = int(self._mqtt_handler.get_entity("current_max_charging").state)

       _LOGGER.info(f"command message = {message} new_values={new_values} new_version={new_version}")

       self._last_command = message;
       return message.build()

    # Send a new message using values on mqtt entities
    async def send_cmd_message_to_juicebox(self, new_values):
       if self.is_mqtt_entity_defined("current_max") and self.is_mqtt_entity_defined("current_max_charging"):
          cmd_message = self.__build_cmd_message(new_values)
          _LOGGER.info(f"Sending command to juicebox {cmd_message} new_values={new_values}")
          await self.send_data(cmd_message.encode('utf-8'), self._juicebox_addr)
       else:
          _LOGGER.warn("Unable to send command to juicebox before current_max and current_max_charging values are set") 

    async def set_mqtt_handler(self, mqtt_handler):
        self._mqtt_handler = mqtt_handler

    async def set_local_mitm_handler(self, local_mitm_handler):
        self._local_mitm_handler = local_mitm_handler

    async def set_remote_mitm_handler(self, remote_mitm_handler):
        self._remote_mitm_handler = remote_mitm_handler

    async def _add_error(self):
        self._error_timestamp_list.append(time.time())
        time_cutoff = time.time() - (ERROR_LOOKBACK_MIN * 60)
        temp_list = list(
            filter(lambda el: el > time_cutoff, self._error_timestamp_list)
        )
        self._error_timestamp_list = temp_list
        self._error_count = len(self._error_timestamp_list)
        _LOGGER.debug(f"Errors in last {ERROR_LOOKBACK_MIN} min: {self._error_count}")
