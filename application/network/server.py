import socket
import asyncio
from abc import ABC, abstractmethod

from application.network.common import to_coroutine_function
from config.logger import logger


class AsyncAbstractServer(ABC):
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._sock = None
        self._server = None
        self._connections = []

    @abstractmethod
    async def start(self):
        ...

    @abstractmethod
    async def stop(self):
        ...


class AsyncAbstractConnection(ABC):
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._reader = None
        self._writer = None

    @abstractmethod
    async def close(self, *args, **kwargs):
        ...

    # @abstractmethod
    # async def read(self, *args, **kwargs):
    #     ...

    @abstractmethod
    async def write(self, *args, **kwargs):
        ...

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def __repr__(self):
        return f"{self.__class__.__name__}({self._host}:{self._port})"


class AsyncTcpConnection(AsyncAbstractConnection):
    def __init__(
        self,
        host: str,
        port: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        super().__init__(host, port)
        self._reader = reader
        self._writer = writer
        self._is_opened = True

    async def close(self, *args, **kwargs):
        self._writer.close()
        await self._writer.wait_closed()
        self._is_opened = False

    async def _read(self, n: int):
        func = to_coroutine_function(self._reader.read)
        return await func(n)

    async def read(self, n: int) -> bytes:
        try:
            res = await self._read(n)
        except ConnectionError:
            self._is_opened = False
            raise
        if not res:
            self._is_opened = False
            raise ConnectionError("Connection closed")
        return res

    async def _write(self, data: bytes):
        func = to_coroutine_function(self._writer.write)
        return await func(data)

    async def write(self, data: bytes):
        try:
            return await self._write(data)
        except ConnectionError:
            self._is_opened = False
            raise

    @property
    def is_opened(self):
        return self._is_opened


class AsyncTcpServer(AsyncAbstractServer):
    def __init__(self, host: str, port: int):
        super().__init__(host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._host, self._port))
        self._connections: list[AsyncTcpConnection] = []

        asyncio.create_task(self._monitoring_connections())

    async def _monitoring_connections(self):
        while True:
            # logger.debug(f"connections: {self._connections}")
            await asyncio.sleep(1)
            for connection in self._connections:
                if not connection.is_opened:
                    logger.debug(f"lost connection {connection}")
                    self._connections.remove(connection)

    async def start(self):
        logger.debug(f"start TCP server {self._host}:{self._port}")
        self._server = await asyncio.start_server(
            self.handle_message, sock=self._sock, start_serving=True
        )
        return await self._server.serve_forever()

    async def stop(self):
        self._server.close()
        await self._server.wait_closed()

    async def handle_message(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        addr = writer.get_extra_info("peername")
        new_connection = AsyncTcpConnection(*addr, reader, writer)
        self._connections.append(new_connection)

    @property
    def connections(self):
        return self._connections


class AsyncUdpConnection(AsyncAbstractConnection):
    def __init__(self, host: str, port: int, transport):
        super().__init__(host, port)
        self._transport = transport
        self._is_opened = True

    def close(self):
        self._writer.close()
        self._is_opened = False

    async def write(self, data: bytes):
        await asyncio.sleep(0)
        self._transport.sendto(data, (self._host, self._port))

    async def is_opened(self):
        return self._is_opened


class UdpConnectionPool(asyncio.DatagramProtocol):
    def __init__(self):
        super().__init__()
        self.transport = None
        self._connections: list[AsyncUdpConnection] = []

    async def _monitoring_connections(self):
        while True:
            await asyncio.sleep(1)
            # logger.debug(f"connections: {self._connections}")
            for connection in self._connections:
                if not connection.is_opened:
                    logger.debug(f"lost connection {connection}")
                    self._connections.remove(connection)

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        addresses = [
            (connection.host, connection.port)
            for connection in self._connections
        ]
        if addr not in addresses:
            connection = AsyncUdpConnection(*addr, self.transport)
            self._connections.append(connection)
        else:
            connection = self._connections[addresses.index(addr)]
        logger.debug(f"{connection} -> {data.decode()}")

    @property
    def connections(self):
        return self._connections


class AsyncUdpServer(AsyncAbstractServer):
    def __init__(self, host: str, port: int):
        super().__init__(host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._host, self._port))
        self._future = None
        self._transport = None
        self._protocol = None

    async def _start(self):
        (
            self._transport,
            self._protocol,
        ) = await asyncio.get_running_loop().create_datagram_endpoint(
            UdpConnectionPool, sock=self._sock
        )
        self._future = asyncio.get_running_loop().create_future()
        await self._future

    async def start(self):
        logger.debug(f"start UDP server {self._host}:{self._port}")
        await self._start()

    async def _stop(self):
        await asyncio.sleep(0)
        self._future.set_result(True)

    async def stop(self):
        await self._stop()

    @property
    def connections(self):
        return self._protocol.connections


if __name__ == "__main__":

    async def serving(server):
        for i in range(10):
            await asyncio.sleep(1)
            logger.debug(server.connections)
            for connection in server.connections:
                await connection.write(f"message {i}".encode())
        await server.stop()

    async def main():
        server = AsyncUdpServer("127.0.0.1", 8000)
        await asyncio.gather(server.start(), serving(server))

    asyncio.run(main())
