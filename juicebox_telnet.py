import asyncio
import logging

import telnetlib3

# import sys

logger = logging.getLogger(__name__)


class JuiceboxTelnet:
    def __init__(self, host, port=2000, timeout=None, loglevel=None):
        # logger.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if loglevel is not None:
            logger.setLevel(loglevel)
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.timeout = timeout
        # logger.debug(f"self.timeout: {self.timeout}")

    async def __aenter__(self):
        # logger.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        # logger.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if self.reader:
            self.reader.close()
        self.reader = None
        if self.writer:
            self.writer.close()
        self.writer = None

    async def read_until(self, match: bytes):
        # logger.debug(f"read_until match: {match}")
        data = b""
        if self.reader is None:
            logger.debug(
                "read_until called but Telnet not connected. Trying to connect"
            )
            await self.open()
            if self.reader is None:
                logger.warning(
                    "read_until called but Telnet not connected. Retry Failed"
                )
                return data
        try:
            async with asyncio.timeout(self.timeout):
                while not data.endswith(match):
                    chunk = await self.reader.read(1)
                    if not chunk:
                        break
                    # logger.debug(f"chunk: {chunk}")
                    if isinstance(chunk, (bytes, bytearray)):
                        data += chunk
                    else:
                        data += str.encode(chunk)
        except asyncio.TimeoutError:
            logger.warning(f"TimeoutError: read_until (data: {data})")
            return data
        # logger.debug(f"read_until data: {data}")
        return data

    async def write(self, data: bytes):
        # logger.debug(f"write data: {data}")
        if self.writer is None:
            logger.debug("write called but Telnet not connected. Trying to connect")
            await self.open()
            if self.writer is None:
                logger.warning("write called but Telnet not connected. Retry Failed")
                return False
        try:
            async with asyncio.timeout(self.timeout):
                # logger.debug(f"self.writer type check 2: {type(self.writer)}")
                self.writer.write(data)
                await self.writer.drain()
        except TimeoutError:
            logger.warning("TimeoutError: write")
            return False
        return True

    async def open(self):
        # logger.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        if self.reader is None or self.writer is None:
            try:
                async with asyncio.timeout(self.timeout):
                    self.reader, self.writer = await telnetlib3.open_connection(
                        self.host, self.port, encoding=False
                    )
                await self.read_until(b">")
            except TimeoutError:
                logger.warning("TimeoutError: Open Telnet Connection Failed")
                return False
        # logger.debug("Telnet Opened")
        return True

    async def list(self):
        # logger.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        await self.open()
        await self.write(b"\n")
        await self.read_until(b"> ")
        await self.write(b"list\n")
        await self.read_until(b"list\r\n! ")
        res = await self.read_until(b">")
        lines = str(res[:-3]).split("\\r\\n")
        out = []
        for line in lines[1:]:
            parts = line.split(" ")
            if len(parts) >= 5:
                out.append({"id": parts[1], "type": parts[2], "dest": parts[4]})
        return out

    async def get_variable(self, variable) -> bytes:
        # logger.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        await self.open()
        await self.write(b"\n")
        await self.read_until(b"> ")
        cmd = f"get {variable}\r\n".encode("ascii")
        await self.write(cmd)
        await self.read_until(cmd)
        res = await self.read_until(b">")
        return res[:-1].strip()

    async def get_all(self):
        # logger.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        await self.open()
        await self.write(b"\n")
        await self.read_until(b">")
        cmd = "get all\r\n".encode("ascii")
        await self.write(cmd)
        await self.read_until(cmd)
        res = await self.read_until(b">")
        lines = str(res[:-1]).split("\\r\\n")
        vars = {}
        for line in lines:
            parts = line.split(": ")
            if len(parts) == 2:
                vars[parts[0]] = parts[1]
        return vars

    async def stream_close(self, id):
        # logger.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        await self.open()
        await self.write(b"\n")
        await self.read_until(b">")
        await self.write(f"stream_close {id}\n".encode("ascii"))
        await self.read_until(b">")

    async def write_udpc(self, host, port):
        # logger.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        await self.open()
        await self.write(b"\n")
        await self.read_until(b">")
        await self.write(f"udpc {host} {port}\n".encode("ascii"))
        await self.read_until(b">")

    async def save(self):
        # logger.debug(f"JuiceboxTelnet Function: {sys._getframe().f_code.co_name}")
        await self.open()
        await self.write(b"\n")
        await self.read_until(b">")
        await self.write(b"save\n")
        await self.read_until(b">")
