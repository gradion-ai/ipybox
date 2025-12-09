import asyncio
import socket
from functools import partial
from typing import Callable, TypeVar

T = TypeVar("T")


async def arun(func: Callable[..., T], *args, **kwargs) -> T:
    return await asyncio.get_running_loop().run_in_executor(None, partial(func, *args, **kwargs))


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]
