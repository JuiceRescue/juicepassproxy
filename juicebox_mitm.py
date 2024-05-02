from __future__ import annotations

import asyncio
import errno
import logging

import asyncio_dgram

# import sys

# https://github.com/rsc-dev/pyproxy MIT
# https://github.com/lucas-six/python-cookbook Apache 2.0
# https://github.com/dannerph/keba-kecontact MIT

_LOGGER = logging.getLogger(__name__)


class JuiceboxMITM:

    def __init__(
        self,
        jpp_addr,
        enelx_addr,
        local_mitm_handler=None,
        ignore_remote=False,
        remote_mitm_handler=None,
        mqtt_handler=None,
        loglevel=None,
    ):
        # _LOGGER.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        if loglevel is not None:
            _LOGGER.setLevel(loglevel)
        self.jpp_addr = self.ip_to_tuple(jpp_addr)
        self.enelx_addr = self.ip_to_tuple(enelx_addr)
        self.juicebox_addr = None
        self.ignore_remote = ignore_remote
        self.local_mitm_handler = local_mitm_handler
        self.remote_mitm_handler = remote_mitm_handler
        self._mqtt_handler = mqtt_handler
        self._loop = asyncio.get_running_loop()
        self._sending_lock = asyncio.Lock()
        self._stream = None

    async def start(self) -> None:
        # _LOGGER.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        _LOGGER.info("Starting JuiceboxMITM")
        _LOGGER.debug(f"JPP: {self.jpp_addr[0]}:{self.jpp_addr[1]}")
        _LOGGER.debug(f"EnelX: {self.enelx_addr[0]}:{self.enelx_addr[1]}")

        # Block sending until stream is setup
        async with self._sending_lock:
            if self._stream is not None:
                return

            self._stream = await asyncio_dgram.bind(self.jpp_addr)

            async def listen() -> None:
                data, remote_addr = await self._stream.recv()
                self._loop.create_task(listen())
                self._loop.create_task(self.main_mitm_handler(data, remote_addr))

            self._loop.create_task(listen())
            _LOGGER.debug(
                f"JuiceboxMITM Socket binding created and listening started. {
                    self.jpp_addr}"
            )

    async def main_mitm_handler(self, data: bytes, from_addr: tuple[str, int]):
        # _LOGGER.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")

        while self._stream.exception is not None:
            pass

        if data is None or from_addr is None:
            return

        # _LOGGER.debug(f"JuiceboxMITM Recv: {data} from {from_addr}")
        if from_addr[0] != self.enelx_addr[0]:
            self.juicebox_addr = from_addr

        if from_addr == self.juicebox_addr:
            data = await self.local_mitm_handler(data)
            if not self.ignore_remote:
                try:
                    await self.send_data(data, self.enelx_addr)
                except OSError as e:
                    _LOGGER.warning(
                        f"JuiceboxMITM OSError {
                            errno.errorcode[e.errno]} [{self.enelx_addr}]: {e}"
                    )
                    await self.local_mitm_handler(
                        f"JuiceboxMITM_OSERROR|server|{self.enelx_addr}|{
                            errno.errorcode[e.errno]}|{e}"
                    )
        elif self.juicebox_addr is not None and from_addr == self.enelx_addr:
            if not self.ignore_remote:
                data = await self.remote_mitm_handler(data)
                try:
                    await self.send_data(data, self.juicebox_addr)
                except OSError as e:
                    _LOGGER.warning(
                        f"JuiceboxMITM OSError {
                            errno.errorcode[e.errno]} [{self.juicebox_addr}]: {e}"
                    )
                    await self.local_mitm_handler(
                        f"JuiceboxMITM_OSERROR|client|{self.juicebox_addr}|{
                            errno.errorcode[e.errno]}|{e}"
                    )
            else:
                _LOGGER.info(f"Ignoring Remote: {data}")
        else:
            _LOGGER.warning(f"JuiceboxMITM Unknown address: {from_addr}")

    async def send_data(
        self, data: bytes, to_addr: tuple[str, int], blocking_time: int = 0.1
    ):
        if self._stream is None:
            _LOGGER.error(
                "JuiceboxMITM Not Connected. Cannot Send: {data} to {to_addr}"
            )
            return

        async with self._sending_lock:
            await self._stream.send(data, to_addr)
            await asyncio.sleep(
                max(blocking_time, 0.1)
            )  # Sleep for blocking time but at least 100 ms

        while self._stream.exception is not None:
            pass

        # _LOGGER.debug(f"JuiceboxMITM Sent: {data} to {to_addr}")

    async def send_data_to_juicebox(self, data: bytes):
        # _LOGGER.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        await self.send_data(data, self.juicebox_addr)

    async def set_mqtt_handler(self, mqtt_handler):
        self._mqtt_handler = mqtt_handler

    async def set_local_mitm_handler(self, local_mitm_handler):
        # _LOGGER.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        self.local_mitm_handler = local_mitm_handler

    async def set_remote_mitm_handler(self, remote_mitm_handler):
        # _LOGGER.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        self.remote_mitm_handler = remote_mitm_handler

    def ip_to_tuple(self, ip):
        # _LOGGER.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        ip, port = ip.split(":")
        return (ip, int(port))
