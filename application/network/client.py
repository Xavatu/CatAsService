import socket
import asyncio
from abc import ABC, abstractmethod

from application.network.common import to_coroutine_function, Reader, Writer


class AsyncAbstractClient(ABC):
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._sock = None
        self._reader = None
        self._writer = None

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @abstractmethod
    async def open(self, *args, **kwargs) -> "AsyncAbstractClient":
        ...

    @abstractmethod
    async def close(self, *args, **kwargs):
        ...

    @abstractmethod
    async def read(self, *args, **kwargs):
        ...

    @abstractmethod
    async def write(self, *args, **kwargs):
        ...


class AsyncTransportClient(AsyncAbstractClient):
    def __init__(self, host: str, port: int, sock: socket.socket):
        super().__init__(host, port)
        self._sock = sock
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._host, self._port))

    async def open(
        self, host: str, port: int, **kwargs
    ) -> "AsyncTransportClient":
        self._sock.connect((host, port))
        self._reader, self._writer = await asyncio.open_connection(
            sock=self._sock
        )
        return self

    async def close(self, force: bool = False):
        if not force:
            self._sock.shutdown(socket.SHUT_RDWR)
        self._writer.close()
        await self._writer.wait_closed()

    @property
    def is_opened(self) -> bool:
        return False if self._sock.fileno() == -1 else True

    async def _read(self, n: int):
        func = to_coroutine_function(self._reader.read)
        return await func(n)

    async def read(self, n: int) -> bytes:
        return await self._read(n)

    async def _write(self, data: bytes):
        func = to_coroutine_function(self._writer.write)
        return await func(data)

    async def write(self, data: bytes):
        await self._write(data)
        # await self._writer.drain()


class AsyncTcpClient(AsyncTransportClient):
    def __init__(self, host: str, port: int):
        super().__init__(
            host, port, socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        )


class AsyncUdpClient(AsyncTransportClient):
    def __init__(self, host: str, port: int):
        super().__init__(
            host, port, socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        )

    async def open(
        self, host: str, port: int, **kwargs
    ) -> "AsyncTransportClient":
        await asyncio.sleep(0)
        self._sock.connect((host, port))
        self._reader = Reader(self._sock)
        self._writer = Writer(self._sock)
        return self


if __name__ == "__main__":

    async def main():
        client = AsyncTcpClient("127.0.0.1", 8011)
        await client.open("127.0.0.1", 8000)
        while True:
            await client.write("123@Alex~@Sta".encode())
            await asyncio.sleep(1)
            data = await client.read(100)
            print(f"Received: {data.decode()!r}")

    asyncio.run(main())
