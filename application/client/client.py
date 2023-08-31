import socket
import asyncio
from abc import ABC, abstractmethod
from functools import wraps


class AsyncAbstractClient(ABC):
    def __init__(self, host: str, port: str):
        self._host = host
        self._port = port
        self._sock = None
        self._reader = None
        self._writer = None

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> str:
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


def to_coroutine_function(func):
    if asyncio.iscoroutinefunction(func):
        return func

    @wraps(func)
    async def wrapper(*args, **kwargs):
        await asyncio.sleep(0)
        return func(*args, **kwargs)

    return wrapper


class AsyncTransportClient(AsyncAbstractClient):
    def __init__(self, host: str, port: str, sock: socket.socket):
        super().__init__(host, port)
        self._sock = sock
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._host, int(self._port)))

    async def open(
        self, host: str, port: str, **kwargs
    ) -> "AsyncTransportClient":
        self._sock.connect((host, int(port)))
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


class TcpTransportClient(AsyncTransportClient):
    def __init__(self, host: str, port: str):
        super().__init__(
            host, port, socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        )


class _Reader:
    def __init__(self, sock: socket.socket):
        self._sock = sock

    def read(self, n: int, **kwargs) -> bytes:
        return self._sock.recv(n, **kwargs)


class _Writer:
    def __init__(self, sock: socket.socket):
        self._sock = sock

    def write(self, data: bytes, **kwargs):
        self._sock.send(data, **kwargs)


class UdpTransportClient(AsyncTransportClient):
    def __init__(self, host: str, port: str):
        super().__init__(
            host, port, socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        )

    async def open(
        self, host: str, port: str, **kwargs
    ) -> "AsyncTransportClient":
        await asyncio.sleep(0)
        self._sock.connect((host, int(port)))
        self._reader = _Reader(self._sock)
        self._writer = _Writer(self._sock)
        return self


if __name__ == "__main__":

    async def main():
        client = UdpTransportClient("127.0.0.1", "8002")
        await client.open("127.0.0.1", "8889")
        await client.write("Hello World!".encode())
        data = await client.read(100)
        print(f"Received: {data.decode()!r}")
        await client.close()

    asyncio.run(main())
