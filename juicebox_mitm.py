from __future__ import annotations

import asyncio
import errno
import logging
import socket

# import sys

# https://github.com/rsc-dev/pyproxy MIT
# https://github.com/lucas-six/python-cookbook Apache 2.0

logger = logging.getLogger(__name__)

recv_bufsize: int | None = None
send_bufsize: int | None = None


class JuiceboxMITM_RecvProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        jpp_addr: tuple[str, int],
        enelx_addr: tuple[str, int],
        main_mitm_handler,
        on_con_lost: asyncio.Future[bool],
    ):
        # logger.debug(f"JuiceboxMITM_RecvProtocol Function: {sys._getframe().f_code.co_name}")
        self.main_mitm_handler = main_mitm_handler
        self.on_con_lost = on_con_lost
        self.loop = asyncio.get_running_loop()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        # logger.debug(f"JuiceboxMITM_RecvProtocol Function: {sys._getframe().f_code.co_name}")
        self.transport = transport
        sock = transport.get_extra_info("socket")
        addr = transport.get_extra_info("sockname")
        assert sock.getsockname() == addr

    def datagram_received(self, data: bytes, from_addr: tuple[str, int]) -> None:
        self.loop.create_task(self.datagram_received_async(data, from_addr))

    async def datagram_received_async(
        self, data: bytes, from_addr: tuple[str, int]
    ) -> None:
        # logger.debug(f"JuiceboxMITM_RecvProtocol Function: {sys._getframe().f_code.co_name}")
        assert self.transport
        sock = self.transport.get_extra_info("socket")
        assert sock.type is socket.SOCK_DGRAM
        assert not sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        assert sock.gettimeout() == 0.0
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        # logger.debug(f"JuiceboxMITM_RecvProtocol Recv: {data} from {addr}")
        await self.main_mitm_handler(data, from_addr)

    def error_received(self, e: Exception | None) -> None:
        # logger.debug(f"JuiceboxMITM_RecvProtocol Function: {sys._getframe().f_code.co_name}")
        logger.error(
            f"JuiceboxMITM_RecvProtocol Error received. ({e.__class__.__qualname__}: {
                e})"
        )

    def connection_lost(self, e: Exception | None) -> None:
        # logger.debug(f"JuiceboxMITM_RecvProtocol Function: {sys._getframe().f_code.co_name}")
        if e is not None:
            logger.error(
                f"JuiceboxMITM_RecvProtocol Connection Lost. ({e.__class__.__qualname__}: {
                    e})"
            )
        if not self.on_con_lost.cancelled():
            self.on_con_lost.set_result(True)


class JuiceboxMITM_SendProtocol(asyncio.DatagramProtocol):
    def __init__(
        self, data: bytes, main_mitm_handler, on_con_lost: asyncio.Future[bool]
    ) -> None:
        # logger.debug(f"JuiceboxMITM_SendProtocol Function: {sys._getframe().f_code.co_name}")
        self.data = data
        self.on_con_lost = on_con_lost
        self.transport: asyncio.DatagramTransport | None = None
        self.main_mitm_handler = main_mitm_handler
        self.loop = asyncio.get_running_loop()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        # logger.debug(f"JuiceboxMITM_SendProtocol Function: {sys._getframe().f_code.co_name}")
        self.transport = transport
        sock = transport.get_extra_info("socket")
        addr = transport.get_extra_info("peername")
        assert sock.getpeername() == addr

        transport.sendto(self.data)
        # logger.debug(f"JuiceboxMITM_SendProtocol Sent: {self.data} to {addr}")

    def datagram_received(self, data: bytes, from_addr: tuple[str, int]) -> None:
        self.loop.create_task(self.datagram_received_async(data, from_addr))

    async def datagram_received_async(
        self, data: bytes, from_addr: tuple[str, int]
    ) -> None:
        # logger.debug(f"JuiceboxMITM_SendProtocol Function: {sys._getframe().f_code.co_name}")
        assert self.transport
        sock = self.transport.get_extra_info("socket")
        assert sock.type is socket.SOCK_DGRAM
        assert not sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        assert sock.gettimeout() == 0.0
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        # logger.debug(f"JuiceboxMITM_SendProtocol Recv: {data} from {addr}")
        await self.main_mitm_handler(data, from_addr)

    def error_received(self, e: Exception | None) -> None:
        # logger.debug(f"JuiceboxMITM_SendProtocol Function: {sys._getframe().f_code.co_name}")
        logger.error(
            f"JuiceboxMITM_SendProtocol Error received. ({e.__class__.__qualname__}: {
                e})"
        )

    def connection_lost(self, e: Exception | None) -> None:
        # logger.debug(f"JuiceboxMITM_SendProtocol Function: {sys._getframe().f_code.co_name}")
        if e is not None:
            logger.error(
                f"JuiceboxMITM_SendProtocol Connection Lost. ({e.__class__.__qualname__}: {
                    e})"
            )
        if not self.on_con_lost.cancelled():
            self.on_con_lost.set_result(True)


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
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        if loglevel is not None:
            logger.setLevel(loglevel)
        self.jpp_addr = self.ip_to_tuple(jpp_addr)
        self.enelx_addr = self.ip_to_tuple(enelx_addr)
        self.ignore_remote = ignore_remote
        self.local_mitm_handler = local_mitm_handler
        self.remote_mitm_handler = remote_mitm_handler
        self._mqtt_handler = mqtt_handler
        self.juicebox_addr = None
        self.loop = asyncio.get_running_loop()

    async def start(self) -> None:
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        logger.info("Starting JuiceboxMITM")
        logger.debug(f"JPP: {self.jpp_addr[0]}:{self.jpp_addr[1]}")
        logger.debug(f"EnelX: {self.enelx_addr[0]}:{self.enelx_addr[1]}")

        on_con_lost = self.loop.create_future()
        udp_mitm, _ = await self.loop.create_datagram_endpoint(
            lambda: JuiceboxMITM_RecvProtocol(
                self.jpp_addr, self.enelx_addr, self.main_mitm_handler, on_con_lost
            ),
            local_addr=self.jpp_addr,
            reuse_port=True,
        )
        try:
            await on_con_lost
        finally:
            udp_mitm.close()

    async def set_mqtt_handler(self, mqtt_handler):
        logger.debug(f"mqtt_handler type: {type(mqtt_handler)}")
        self._mqtt_handler = mqtt_handler

    async def send_data(self, data: bytes, to_addr: tuple[str, int]):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        if data is None or to_addr is None:
            return None
        on_con_lost = self.loop.create_future()

        # logger.debug(f"sending: {data}, to: {addr}")
        udp_send, _ = await self.loop.create_datagram_endpoint(
            lambda: JuiceboxMITM_SendProtocol(
                data, self.main_mitm_handler, on_con_lost
            ),
            remote_addr=to_addr,
        )
        try:
            await on_con_lost
        finally:
            udp_send.close()

    async def send_data_to_juicebox(self, data: bytes):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        if data is None or self.juicebox_addr is None:
            return None
        on_con_lost = self.loop.create_future()

        logger.debug(f"Sending to Juicebox: {data} to: {self.juicebox_addr}")
        udp_send, _ = await self.loop.create_datagram_endpoint(
            lambda: JuiceboxMITM_SendProtocol(
                data, self.main_mitm_handler, on_con_lost
            ),
            remote_addr=self.juicebox_addr,
        )
        try:
            await on_con_lost
        finally:
            udp_send.close()

    async def main_mitm_handler(self, data: bytes, from_addr: tuple[str, int]):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        if data is None or from_addr is None:
            return None

        if from_addr[0] != self.enelx_addr[0]:
            self.juicebox_addr = from_addr
            # logger.debug(f"self.juicebox_addr: {self.juicebox_addr}")

        if from_addr == self.juicebox_addr:
            data = await self.local_mitm_handler(data)
            if not self.ignore_remote:
                try:
                    await self.send_data(data, self.enelx_addr)
                except OSError as e:
                    logger.warning(
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
                    logger.warning(
                        f"JuiceboxMITM OSError {
                            errno.errorcode[e.errno]} [{self.juicebox_addr}]: {e}"
                    )
                    await self.local_mitm_handler(
                        f"JuiceboxMITM_OSERROR|client|{self.juicebox_addr}|{
                            errno.errorcode[e.errno]}|{e}"
                    )
            else:
                logger.info(f"Ignoring Remote: {data}")
        else:
            logger.warning(f"JuiceboxMITM Unknown address: {from_addr}")

    async def set_local_mitm_handler(self, x):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        self.local_mitm_handler = x

    async def set_remote_mitm_handler(self, x):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        self.remote_mitm_handler = x

    def ip_to_tuple(self, ip):
        """Parse IP string and return (ip, port) tuple.

        Arguments:
        ip -- IP address:port string. I.e.: '127.0.0.1:8000'.
        """
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        ip, port = ip.split(":")
        return (ip, int(port))
