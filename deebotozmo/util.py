"""Util module."""
import asyncio
import copy
import hashlib
import os
from typing import Awaitable, Callable, List, Union

from deebotozmo.commands import Command
from deebotozmo.commands_old import Command as OldCommand


def str_to_bool_or_cert(string: Union[bool, str]) -> Union[bool, str]:
    """Convert string to bool or certificate."""
    if string == "True" or string is True:
        return True

    if string == "False" or string is False:
        return False

    if string is not None:
        if os.path.exists(str(string)):
            # User could provide a path to a CA Cert as well, which is useful for Bumper
            if os.path.isfile(str(string)):
                return string
            raise ValueError(f"Certificate path provided is not a file: {string}")

    raise ValueError(f'Cannot convert "{string}" to a bool or certificate path')


def md5(text: str) -> str:
    """Hash text using md5."""
    return hashlib.md5(bytes(str(text), "utf8")).hexdigest()


def get_refresh_function(
    commands: List[Union[Command, OldCommand]],
    execute_command: Callable[[Union[Command, OldCommand]], Awaitable[None]],
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


def sanitize_data(data: dict) -> dict:
    """Sanitize data (remove personal data)."""
    sanitized_data = copy.deepcopy(data)
    for key in ["auth", "token", "userId", "userid", "accessToken", "uid", "toId"]:
        if key in sanitized_data:
            sanitized_data[key] = "[REMOVED]"

    return sanitized_data
