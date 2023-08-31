import socket
import asyncio
from abc import ABC, abstractmethod
from functools import wraps

from application.network.client import to_coroutine_function


class AsyncAbstractServer(ABC):
    def __init__(self, host: str, port: str):
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

    # @abstractmethod
    # async def read(self, *args, **kwargs):
    #     ...
    #
    # @abstractmethod
    # async def write(self, *args, **kwargs):
    #     ...

    @abstractmethod
    async def handle_message(self, *args, **kwargs):
        ...


class AsyncAbstractConnection(ABC):
    def __init__(self, host: str, port: str):
        self._host = host
        self._port = port
        self._reader = None
        self._writer = None

    @abstractmethod
    async def close(self, *args, **kwargs):
        ...

    @abstractmethod
    async def read(self, *args, **kwargs):
        ...

    @abstractmethod
    async def write(self, *args, **kwargs):
        ...


class AsyncTransportConnection(AsyncAbstractConnection):
    def __init__(
        self,
        host: str,
        port: str,
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

    def _handle_connection_error(self, func):
        # check func is coroutine or awaitable
        if not hasattr(func, "__await__"):

            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except ConnectionError:
                    self._is_opened = False
                    raise

            return wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ConnectionError:
                self._is_opened = False
                raise

        return wrapper

    async def _read(self, n: int):
        func = to_coroutine_function(self._reader.read)
        return await func(n)

    @_handle_connection_error
    async def read(self, n: int) -> bytes:
        return await self._read(n)

    async def _write(self, data: bytes):
        func = to_coroutine_function(self._writer.write)
        return await func(data)

    @_handle_connection_error
    async def write(self, data: bytes):
        return await self._write(data)

    @property
    def is_opened(self):
        return self._is_opened


class AsyncTransportServer(AsyncAbstractServer):
    def __init__(self, host: str, port: str, sock: socket.socket):
        super().__init__(host, port)
        self._sock = sock
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._host, int(self._port)))
        self._connections: list[AsyncTransportConnection] = []

        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(self._monitoring_connections())

    async def _monitoring_connections(self):
        while True:
            await asyncio.sleep(1)
            for connection in self._connections:
                if not connection.is_opened:
                    print(f"connection lost {connection}")
                    del connection

    async def start(self):
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
        new_connection = AsyncTransportConnection(*addr, reader, writer)
        self._connections.append(new_connection)

    @property
    def connections(self):
        return self._connections


class AsyncTcpServer(AsyncTransportServer):
    def __init__(self, host: str, port: str):
        super().__init__(
            host, port, socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        )


if __name__ == "__main__":
    server = AsyncTcpServer("127.0.0.1", "8000")

    async def start_server():
        await server.start()

    async def stop_server():
        while True:
            await asyncio.sleep(1)
            print(server.connections)

    async def main():
        await asyncio.gather(start_server(), stop_server())

    asyncio.run(main())
