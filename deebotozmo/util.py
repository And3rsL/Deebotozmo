"""Util module."""
import asyncio
import copy
import hashlib
from typing import Awaitable, Callable, List, Set

from deebotozmo.commands import Command


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
