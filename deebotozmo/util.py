import asyncio
import hashlib
import os
from typing import Union, TypeVar, Callable, Awaitable, Type

from deebotozmo.commands import Command
from deebotozmo.events import PollingEventEmitter, EventEmitter


def str_to_bool_or_cert(s: Union[bool, str]) -> Union[bool, str]:
    if s == "True" or s is True:
        return True
    elif s == "False" or s is False:
        return False
    else:
        if s is not None:
            if os.path.exists(s):
                # User could provide a path to a CA Cert as well, which is useful for Bumper
                if os.path.isfile(s):
                    return s
                else:
                    raise ValueError(f"Certificate path provided is not a file: {s}")

        raise ValueError(f"Cannot covert \"{s}\" to a bool or certificate path")


def md5(text):
    return hashlib.md5(bytes(str(text), "utf8")).hexdigest()


def get_refresh_function(commands: [Command], execute_command: Callable[[Command], Awaitable[None]]) -> \
        Callable[[], Awaitable[None]]:
    if len(commands) == 1:
        async def refresh():
            await execute_command(commands[0])
    else:
        async def refresh():
            tasks = []
            for c in commands:
                tasks.append(asyncio.create_task(execute_command(c)))

            await asyncio.gather(*tasks)

    return refresh


T = TypeVar('T')


def get_EventEmitter(event_type: Type[T], commands: [Command],
                     execute_command: Callable[[Command], Awaitable[None]]) -> EventEmitter[T]:
    return EventEmitter[event_type](get_refresh_function(commands, execute_command))


def get_PollingEventEmitter(event_type: Type[T], refresh_interval: int, commands: [Command],
                            execute_command: Callable[[Command], Awaitable[None]], vacuum_bot: "VacuumBot") -> \
        PollingEventEmitter[T]:
    return PollingEventEmitter[event_type](refresh_interval, get_refresh_function(commands, execute_command),
                                           vacuum_bot)
