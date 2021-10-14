"""Util module."""
import asyncio
import copy
import hashlib
import os
from distutils.util import strtobool
from typing import Awaitable, Callable, List, Set, Union

from deebotozmo.commands import Command


def str_to_bool_or_cert(value: Union[bool, str]) -> Union[bool, str]:
    """Convert string to bool or certificate."""
    if isinstance(value, bool):
        return value

    try:
        return strtobool(value)
    except ValueError:
        pass

    if value is not None:
        if os.path.exists(str(value)):
            # User could provide a path to a CA Cert as well, which is useful for Bumper
            if os.path.isfile(str(value)):
                return value
            raise ValueError(f"Certificate path provided is not a file: {value}")

    raise ValueError(f'Cannot convert "{value}" to a bool or certificate path')


def md5(text: str) -> str:
    """Hash text using md5."""
    return hashlib.md5(bytes(str(text), "utf8")).hexdigest()


def get_refresh_function(
    commands: List[Command],
    execute_command: Callable[[Command], Awaitable[None]],
) -> Callable[[], Awaitable[None]]:
    """Return refresh function for given commands."""
    if len(commands) == 1:

        async def refresh() -> None:
            await execute_command(commands[0])

    else:

        async def refresh() -> None:
            tasks = []
            for command in commands:
                tasks.append(asyncio.create_task(execute_command(command)))

            await asyncio.gather(*tasks)

    return refresh


# all lowercase
_SANITIZE_LOG_KEYS: Set[str] = {
    "auth",
    "token",
    "id",
    "login",
    "mobile",
    "user",
    "email",
}


def sanitize_data(data: dict) -> dict:
    """Sanitize data (remove personal data)."""
    sanitized_data = copy.deepcopy(data)
    for key in sanitized_data.keys():
        if any(substring in key.lower() for substring in _SANITIZE_LOG_KEYS):
            sanitized_data[key] = "[REMOVED]"

    return sanitized_data
