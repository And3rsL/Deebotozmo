"""Util module."""
import asyncio
import copy
import hashlib
import os
from typing import Awaitable, Callable, List, Union

from deebotozmo.commands import Command


def str_to_bool_or_cert(s: Union[bool, str]) -> Union[bool, str]:
    """Convert string to bool or certificate."""
    if s == "True" or s is True:
        return True
    elif s == "False" or s is False:
        return False
    else:
        if s is not None:
            if os.path.exists(str(s)):
                # User could provide a path to a CA Cert as well, which is useful for Bumper
                if os.path.isfile(str(s)):
                    return s
                else:
                    raise ValueError(f"Certificate path provided is not a file: {s}")

        raise ValueError(f'Cannot convert "{s}" to a bool or certificate path')


def md5(text: str) -> str:
    """Hash text using md5."""
    return hashlib.md5(bytes(str(text), "utf8")).hexdigest()


def get_refresh_function(
        commands: List[Command], execute_command: Callable[[Command], Awaitable[None]]
) -> Callable[[], Awaitable[None]]:
    """Return refresh function for given commands."""
    if len(commands) == 1:

        async def refresh() -> None:
            await execute_command(commands[0])

    else:

        async def refresh() -> None:
            tasks = []
            for c in commands:
                tasks.append(asyncio.create_task(execute_command(c)))

            await asyncio.gather(*tasks)

    return refresh


def sanitize_data(data: dict) -> dict:
    """Sanitize data (remove personal data)."""
    sanitized_data = copy.deepcopy(data)
    for s in ["auth", "token", "userId", "userid", "accessToken", "uid"]:
        if s in sanitized_data:
            sanitized_data[s] = "[REMOVED]"

    return sanitized_data
