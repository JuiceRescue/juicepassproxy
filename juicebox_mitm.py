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
        src_addr: tuple[str, int],
        dst_addr: tuple[str, int],
        handler,
        on_con_lost: asyncio.Future[bool],
    ):
        # logger.debug(f"JuiceboxMITM_RecvProtocol Function: {sys._getframe().f_code.co_name}")
        self.handler = handler
        self.on_con_lost = on_con_lost
        self.loop = asyncio.get_running_loop()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        # logger.debug(f"JuiceboxMITM_RecvProtocol Function: {sys._getframe().f_code.co_name}")
        self.transport = transport
        sock = transport.get_extra_info("socket")
        addr = transport.get_extra_info("sockname")
        assert sock.getsockname() == addr

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.loop.create_task(self.datagram_received_async(data, addr))

    async def datagram_received_async(self, data: bytes, addr: tuple[str, int]) -> None:
        # logger.debug(f"JuiceboxMITM_RecvProtocol Function: {sys._getframe().f_code.co_name}")
        assert self.transport
        sock = self.transport.get_extra_info("socket")
        assert sock.type is socket.SOCK_DGRAM
        assert not sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        assert sock.gettimeout() == 0.0
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        # logger.debug(f"JuiceboxMITM_RecvProtocol Recv: {data} from {addr}")
        await self.handler(data, addr)

    def connection_lost(self, exc: Exception | None) -> None:
        # logger.debug(f"JuiceboxMITM_RecvProtocol Function: {sys._getframe().f_code.co_name}")
        if not self.on_con_lost.cancelled():
            self.on_con_lost.set_result(True)


class JuiceboxMITM_SendProtocol(asyncio.DatagramProtocol):
    def __init__(self, data: bytes, handler, on_con_lost: asyncio.Future[bool]) -> None:
        # logger.debug(f"JuiceboxMITM_SendProtocol Function: {sys._getframe().f_code.co_name}")
        self.data = data
        self.on_con_lost = on_con_lost
        self.transport: asyncio.DatagramTransport | None = None
        self.handler = handler
        self.loop = asyncio.get_running_loop()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        # logger.debug(f"JuiceboxMITM_SendProtocol Function: {sys._getframe().f_code.co_name}")
        self.transport = transport
        sock = transport.get_extra_info("socket")
        addr = transport.get_extra_info("peername")
        assert sock.getpeername() == addr

        transport.sendto(self.data)
        # logger.debug(f"JuiceboxMITM_SendProtocol Sent: {self.data} to {addr}")

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.loop.create_task(self.datagram_received_async(data, addr))

    async def datagram_received_async(self, data: bytes, addr: tuple[str, int]) -> None:
        # logger.debug(f"JuiceboxMITM_SendProtocol Function: {sys._getframe().f_code.co_name}")
        assert self.transport
        sock = self.transport.get_extra_info("socket")
        assert sock.type is socket.SOCK_DGRAM
        assert not sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        assert sock.gettimeout() == 0.0
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        # logger.debug(f"JuiceboxMITM_SendProtocol Recv: {data} from {addr}")
        await self.handler(data, addr)

    def error_received(self, exc: Exception | None) -> None:
        # logger.debug(f"JuiceboxMITM_SendProtocol Function: {sys._getframe().f_code.co_name}")
        logger.error(f"JuiceboxMITM_SendProtocol Error received: {exc}")

    def connection_lost(self, exc: Exception | None) -> None:
        # logger.debug(f"JuiceboxMITM_SendProtocol Function: {sys._getframe().f_code.co_name}")
        if not self.on_con_lost.cancelled():
            self.on_con_lost.set_result(True)


class JuiceboxMITM:
    def __init__(
        self,
        src_addr,
        dst_addr,
        local_data_handler=None,
        ignore_remote=False,
        remote_data_handler=None,
        mqtt_handler=None,
        loglevel=None,
    ):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        if loglevel is not None:
            logger.setLevel(loglevel)
        self.src_addr = self.ip_to_tuple(src_addr)
        self.dst_addr = self.ip_to_tuple(dst_addr)
        self.ignore_remote = ignore_remote
        self.local_data_handler = local_data_handler
        self.remote_data_handler = remote_data_handler
        self.mqtt_handler = mqtt_handler
        self.client_address = None
        self.loop = asyncio.get_running_loop()

    async def start(self) -> None:
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        logger.info("Starting JuiceboxMITM")
        logger.debug(f"Src: {self.src_addr[0]}:{self.src_addr[1]}")
        logger.debug(f"Dst: {self.dst_addr[0]}:{self.dst_addr[1]}")

        on_con_lost = self.loop.create_future()
        udp_mitm, _ = await self.loop.create_datagram_endpoint(
            lambda: JuiceboxMITM_RecvProtocol(
                self.src_addr, self.dst_addr, self.handler, on_con_lost
            ),
            local_addr=self.src_addr,
            reuse_port=True,
        )
        try:
            await on_con_lost
        finally:
            udp_mitm.close()

    async def send_data(self, data: bytes, addr: tuple[str, int]):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        if data is None or addr is None:
            return None
        on_con_lost = self.loop.create_future()

        # logger.debug(f"sending: {data}, to: {addr}")
        udp_send, _ = await self.loop.create_datagram_endpoint(
            lambda: JuiceboxMITM_SendProtocol(data, self.handler, on_con_lost),
            remote_addr=addr,
        )

        try:
            await on_con_lost
        finally:
            udp_send.close()

    async def send_data_to_local_address(self, data: bytes):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        if data is None:
            return None
        on_con_lost = self.loop.create_future()

        # logger.debug(f"sending: {data}, to: {addr}")
        udp_send, _ = await self.loop.create_datagram_endpoint(
            lambda: JuiceboxMITM_SendProtocol(data, self.handler, on_con_lost),
            remote_addr=self.client_address,
        )

        try:
            await on_con_lost
        finally:
            udp_send.close()

    async def handler(self, data: bytes, from_addr: tuple[str, int]):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        if data is None or from_addr is None:
            return None

        if from_addr[0] != self.dst_addr[0]:
            self.client_address = from_addr
            # logger.debug(f"self.client_address: {self.client_address}")

        if from_addr == self.client_address:
            data = await self.local_data_handler(data)
            if not self.ignore_remote:
                try:
                    await self.send_data(data, self.dst_addr)
                except OSError as e:
                    logger.warning(
                        f"JuiceboxMITM OSError {
                            errno.errorcode[e.errno]} [{self.dst_addr}]: {e}"
                    )
                    await self.local_data_handler(
                        f"JuiceboxMITM_OSERROR|server|{self.dst_addr}|{
                            errno.errorcode[e.errno]}|{e}"
                    )
        elif self.client_address is not None and from_addr == self.dst_addr:
            if not self.ignore_remote:
                data = await self.remote_data_handler(data)
                try:
                    await self.send_data(data, self.client_address)
                except OSError as e:
                    logger.warning(
                        f"JuiceboxMITM OSError {
                            errno.errorcode[e.errno]} [{self.client_address}]: {e}"
                    )
                    await self.local_data_handler(
                        f"JuiceboxMITM_OSERROR|client|{self.client_address}|{
                            errno.errorcode[e.errno]}|{e}"
                    )
            else:
                logger.info(f"Ignoring Remote: {data}")
        else:
            logger.warning(f"JuiceboxMITM Unknown address: {from_addr}")

    def set_local_data_handler(self, x):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        self.local_data_handler = x

    def set_remote_data_handler(self, x):
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        self.remote_data_handler = x

    def ip_to_tuple(self, ip):
        """Parse IP string and return (ip, port) tuple.

        Arguments:
        ip -- IP address:port string. I.e.: '127.0.0.1:8000'.
        """
        # logger.debug(f"JuiceboxMITM Function: {sys._getframe().f_code.co_name}")
        ip, port = ip.split(":")
        return (ip, int(port))
