import asyncio
from functools import wraps
from socket import socket


def to_coroutine_function(func):
    if asyncio.iscoroutinefunction(func):
        return func

    @wraps(func)
    async def wrapper(*args, **kwargs):
        await asyncio.sleep(0)
        return func(*args, **kwargs)

    return wrapper


class Reader:
    def __init__(self, sock: socket):
        self._sock = sock

    def read(self, n: int, **kwargs) -> bytes:
        return self._sock.recv(n, **kwargs)


class Writer:
    def __init__(self, sock: socket):
        self._sock = sock

    def write(self, data: bytes, **kwargs):
        self._sock.send(data, **kwargs)
