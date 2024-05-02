import asyncio
import logging

import telnetlib3

# import sys

_LOGGER = logging.getLogger(__name__)


class JuiceboxTelnet:
    def __init__(self, host, port=2000, timeout=None, loglevel=None):
        # _LOGGER.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if loglevel is not None:
            _LOGGER.setLevel(loglevel)
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.timeout = timeout
        # _LOGGER.debug(f"self.timeout: {self.timeout}")

    async def __aenter__(self):
        # _LOGGER.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if await self.open():
            return self
        return None

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        # _LOGGER.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if self.reader:
            self.reader.close()
        self.reader = None
        if self.writer:
            self.writer.close()
        self.writer = None

    async def readuntil(self, match: bytes):
        # _LOGGER.debug(f"readuntil match: {match}")
        data = b""
        try:
            async with asyncio.timeout(self.timeout):
                data = await self.reader.readuntil(match)
        except asyncio.TimeoutError:
            _LOGGER.warning(f"TimeoutError: readuntil (match: {match}, data: {data})")
            raise
            return data
        # _LOGGER.debug(f"readuntil data: {data}")
        return data

    async def write(self, data: bytes):
        # _LOGGER.debug(f"write data: {data}")
        try:
            async with asyncio.timeout(self.timeout):
                # _LOGGER.debug(f"self.writer type check 2: {type(self.writer)}")
                self.writer.write(data)
                await self.writer.drain()
        except TimeoutError:
            _LOGGER.warning("TimeoutError: write (data: {data})")
            raise
            return False
        return True

    async def open(self):
        # _LOGGER.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if self.reader is None or self.writer is None:
            try:
                async with asyncio.timeout(self.timeout):
                    self.reader, self.writer = await telnetlib3.open_connection(
                        self.host, self.port, encoding=False
                    )
                await self.readuntil(b">")
            except TimeoutError:
                _LOGGER.warning("TimeoutError: Open Telnet Connection Failed")
                raise
                return False
        # _LOGGER.debug("Telnet Opened")
        return True

    async def list(self):
        # _LOGGER.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        out = []
        if await self.open():
            await self.write(b"\n")
            await self.readuntil(b"> ")
            await self.write(b"list\n")
            await self.readuntil(b"list\r\n! ")
            res = await self.readuntil(b">")
            lines = str(res[:-3]).split("\\r\\n")
            for line in lines[1:]:
                parts = line.split(" ")
                if len(parts) >= 5:
                    out.append({"id": parts[1], "type": parts[2], "dest": parts[4]})
        return out

    async def get_variable(self, variable) -> bytes:
        # _LOGGER.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if await self.open():
            await self.write(b"\n")
            await self.readuntil(b"> ")
            cmd = f"get {variable}\r\n".encode("ascii")
            await self.write(cmd)
            await self.readuntil(cmd)
            res = await self.readuntil(b">")
            return res[:-1].strip()
        return None

    async def get_all(self):
        # _LOGGER.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        vars = {}
        if await self.open():
            await self.write(b"\n")
            await self.readuntil(b">")
            cmd = "get all\r\n".encode("ascii")
            await self.write(cmd)
            await self.readuntil(cmd)
            res = await self.readuntil(b">")
            lines = str(res[:-1]).split("\\r\\n")
            for line in lines:
                parts = line.split(": ")
                if len(parts) == 2:
                    vars[parts[0]] = parts[1]
        return vars

    async def stream_close(self, id):
        # _LOGGER.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if await self.open():
            await self.write(b"\n")
            await self.readuntil(b">")
            await self.write(f"stream_close {id}\n".encode("ascii"))
            await self.readuntil(b">")

    async def write_udpc(self, host, port):
        # _LOGGER.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if await self.open():
            await self.write(b"\n")
            await self.readuntil(b">")
            await self.write(f"udpc {host} {port}\n".encode("ascii"))
            await self.readuntil(b">")

    async def save(self):
        # _LOGGER.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if await self.open():
            await self.write(b"\n")
            await self.readuntil(b">")
            await self.write(b"save\n")
            await self.readuntil(b">")
