#!/usr/bin/env python3
"""Cli module."""
import asyncio
import base64
import configparser
import itertools
import json
import logging
import mimetypes
import os
import platform
import sys
import time
from dataclasses import asdict
from functools import wraps
from typing import Any, Callable, Tuple, Union

import aiohttp
import click

from deebotozmo.commands import (
    Charge,
    CleanCustomArea,
    CleanPause,
    CleanResume,
    CleanSpotArea,
    CleanStart,
    PlaySound,
    SetFanSpeed,
    SetWaterLevel,
)
from deebotozmo.ecovacs_api import EcovacsAPI
from deebotozmo.events import (
    BatteryEvent,
    CleanLogEvent,
    FanSpeedEvent,
    MapEvent,
    RoomsEvent,
    StatsEvent,
    StatusEvent,
    WaterInfoEvent,
)
from deebotozmo.models import Vacuum, VacuumState
from deebotozmo.util import md5
from deebotozmo.vacuum_bot import VacuumBot


def coro(func: Callable) -> Callable:
    """Wrap around a function to run it in coroutine."""

    @wraps(func)
    def wrapper(*args: Tuple, **kwargs: Tuple) -> Any:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(func(*args, **kwargs))

    return wrapper


def config_file() -> str:
    """Return the path to config file."""
    if platform.system() == "Windows" and "APPDATA" in os.environ:
        return os.path.join(str(os.getenv("APPDATA")), "deebotozmo.conf")
    return os.path.expanduser("~/.config/deebotozmo.conf")


def config_file_exists() -> bool:
    """Check if the config file exists."""
    return os.path.isfile(config_file())


def read_config() -> configparser.SectionProxy:
    """Read and parse the config file."""
    parser = configparser.ConfigParser()
    with open(config_file(), encoding="utf-8") as file:
        parser.read_file(itertools.chain(["[global]"], file), source=config_file())
    return parser["global"]


def write_config(config: dict) -> None:
    """Create a new config file."""
    os.makedirs(os.path.dirname(config_file()), exist_ok=True)
    with open(config_file(), "w", encoding="utf-8") as file:
        for key in config:
            file.write(f"{key}={config[key]}\n")


@click.group(chain=True, help="")
@click.option("--debug/--no-debug", default=False)
@click.option("--device", default=None, help="Select a device.")
@click.pass_context
def cli(
    ctx: Union[click.Context, None] = None,
    debug: bool = False,
    device: Union[str, None] = None,
) -> None:
    """Create a click group for nesting subcommands."""
    logging.basicConfig(format="%(name)-10s %(levelname)-8s %(message)s")
    logging.root.setLevel(logging.DEBUG if debug else logging.WARNING)

    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    if isinstance(ctx, click.Context):
        ctx.ensure_object(dict)
        ctx.obj["DEVICE"] = device


@cli.command(name="createconfig", help="logs in with specified email; run this first")
@click.option("--email", prompt="Ecovacs app email")
@click.option("--password", prompt="Ecovacs app password", hide_input=True)
@click.option("--country-code", prompt="your two-letter country code")
@click.option("--continent-code", prompt="your two-letter continent code")
@click.option("--verify-ssl", prompt="Verify SSL for API requests", default=True)
@coro
async def create_config(
    email: str, password: str, country_code: str, continent_code: str, verify_ssl: str
) -> None:
    """Click subcommand to create a new config."""
    if config_file_exists() and not click.confirm("overwrite existing config?"):
        click.echo("Skipping createconfig.")
        sys.exit(0)
    config = {}
    password_hash = md5(password)
    device_id = md5(str(time.time()))
    async with aiohttp.ClientSession() as session:
        try:
            EcovacsAPI(
                session,
                device_id,
                email,
                password_hash,
                continent=continent_code,
                country=country_code,
                verify_ssl=verify_ssl,
            )
        except ValueError as error:
            click.echo(error.args[0])
            sys.exit(1)
    config["email"] = email
    config["password_hash"] = password_hash
    config["device_id"] = device_id
    config["country"] = country_code.lower()
    config["continent"] = continent_code.lower()
    config["verify_ssl"] = verify_ssl
    write_config(config)
    click.echo("Config saved.")
    sys.exit(0)


async def run_with_login(
    device: Union[str, None],
    cmd: Callable,
    cmd_list: Union[list, None] = None,
    cmd_dict: Union[dict, None] = None,
) -> None:
    """Execute a command only."""
    if cmd_list is None:
        cmd_list = []

    if cmd_dict is None:
        cmd_dict = {}

    vacbot = CliUtil()
    try:
        await vacbot.before(device)
        await vacbot.bot.execute_command(cmd(*cmd_list, **cmd_dict))
    finally:
        await vacbot.after()


@cli.command(name="playsound", help="Play welcome sound")
@click.pass_context
@coro
async def play_sound(ctx: click.Context) -> None:
    """Click subcommand that runs the welcome sound."""
    await run_with_login(cmd=PlaySound, device=ctx.obj["DEVICE"])


@cli.command(help="Auto clean")
@click.pass_context
@coro
async def clean(ctx: click.Context) -> None:
    """Click subcommand that runs the auto clean command."""
    await run_with_login(cmd=CleanStart, device=ctx.obj["DEVICE"])


@cli.command(
    name="customarea",
    help='Cleans provided area(s), ex: "-602,1812,800,723"',
    context_settings={"ignore_unknown_options": True},
)
@click.argument("area", type=click.STRING, required=True)
@click.argument("cleanings", type=click.INT, required=False)
@click.pass_context
@coro
async def custom_area(ctx: click.Context, area: str, cleanings: int = 1) -> None:
    """Click subcommand that runs a clean in a custom area."""
    await run_with_login(
        cmd=CleanCustomArea,
        cmd_dict={"map_position": area, "cleanings": cleanings},
        device=ctx.obj["DEVICE"],
    )


@cli.command(
    name="spotarea",
    help='Cleans provided rooms(s), ex: "0,1" | Use GetRooms to see saved numbers',
    context_settings={"ignore_unknown_options": True},
)
@click.argument("rooms", type=click.STRING, required=True)
@click.argument("cleanings", type=click.INT)
@click.pass_context
@coro
async def spot_area(ctx: click.Context, rooms: str, cleanings: int = 1) -> None:
    """Click subcommand that runs a clean in a specific room."""
    await run_with_login(
        cmd=CleanSpotArea,
        cmd_dict={"area": rooms, "cleanings": cleanings},
        device=ctx.obj["DEVICE"],
    )


@cli.command(name="setfanspeed", help="Set Clean Speed")
@click.argument("speed", type=click.STRING, required=True)
@click.pass_context
@coro
async def set_fan_speed(ctx: click.Context, speed: str) -> None:
    """Click subcommand that sets the fan speed."""
    await run_with_login(cmd=SetFanSpeed, cmd_list=[speed], device=ctx.obj["DEVICE"])


@cli.command(name="setwaterlevel", help="Set Water Level")
@click.argument("level", type=click.STRING, required=True)
@click.pass_context
@coro
async def set_water_level(ctx: click.Context, level: str) -> None:
    """Click subcommmand that sets the water level."""
    await run_with_login(cmd=SetWaterLevel, cmd_list=[level], device=ctx.obj["DEVICE"])


@cli.command(help="Returns to charger")
@click.pass_context
@coro
async def charge(ctx: click.Context) -> None:
    """Click subcommand that returns to charger."""
    await run_with_login(cmd=Charge, device=ctx.obj["DEVICE"])


@cli.command(help="Pause the robot")
@click.pass_context
@coro
async def pause(ctx: click.Context) -> None:
    """Click subcommand that pauses the clean."""
    await run_with_login(cmd=CleanPause, device=ctx.obj["DEVICE"])


@cli.command(help="Resume the robot")
@click.pass_context
@coro
async def resume(ctx: click.Context) -> None:
    """Click subcommand that resumes the clean."""
    await run_with_login(cmd=CleanResume, device=ctx.obj["DEVICE"])


@cli.command(name="getcleanlogs", help="Get Clean Logs")
@click.pass_context
@coro
async def get_clean_logs(ctx: click.Context) -> None:
    """Click subcommand that returns clean logs."""
    vacbot = CliUtil()
    try:
        await vacbot.before(ctx.obj["DEVICE"])

        lock = asyncio.Event()

        async def on_clean_event(event: CleanLogEvent) -> None:
            print(json.dumps(asdict(event)))
            lock.set()

        lock.clear()
        listener = vacbot.bot.events.clean_logs.subscribe(on_clean_event)
        await lock.wait()
        listener.unsubscribe()
    finally:
        await vacbot.after()


@cli.command(help="Get robot statuses [Status,Battery,FanSpeed,WaterLevel]")
@click.pass_context
@coro
async def statuses(ctx: click.Context) -> None:
    """Click subcommand that returns the robot status."""
    vacbot = CliUtil()
    try:
        await vacbot.before(ctx.obj["DEVICE"])
        lock = asyncio.Event()

        async def on_status(event: StatusEvent) -> None:
            print(f"Vacuum Available: {event.available}")
            if isinstance(event.state, VacuumState):
                print(f"Vacuum State: {event.state.name}")
            lock.set()

        lock.clear()
        status_listener = vacbot.bot.events.status.subscribe(on_status)
        await lock.wait()
        status_listener.unsubscribe()

        async def on_battery(event: BatteryEvent) -> None:
            print("Battery: " + str(event.value) + "%")
            lock.set()

        lock.clear()
        battery_listener = vacbot.bot.events.battery.subscribe(on_battery)
        await lock.wait()
        battery_listener.unsubscribe()

        async def on_fan_event(event: FanSpeedEvent) -> None:
            print("Fan Speed: " + str(event.speed))
            lock.set()

        lock.clear()
        fan_speed_listener = vacbot.bot.events.fan_speed.subscribe(on_fan_event)
        await lock.wait()
        fan_speed_listener.unsubscribe()

        async def on_water_level(event: WaterInfoEvent) -> None:
            print("Water Level: " + str(event.amount))
            lock.set()

        lock.clear()
        water_level_listener = vacbot.bot.events.water_info.subscribe(on_water_level)
        await lock.wait()
        water_level_listener.unsubscribe()
    finally:
        await vacbot.after()


@cli.command(help="Get stats")
@click.pass_context
@coro
async def stats(ctx: click.Context) -> None:
    """Click subcommand that returns bot stats."""
    vacbot = CliUtil()
    try:
        await vacbot.before(ctx.obj["DEVICE"])

        lock = asyncio.Event()

        async def on_stats_event(event: StatsEvent) -> None:
            print(f"Stats Cid: {event.clean_id}")
            print(f"Stats Area: {event.area}")
            if isinstance(event.time, int):
                print(f"Stats Time: {int(event.time / 60)} minutes")
            print(f"Stats Type: {event.type}")
            lock.set()

        lock.clear()
        listener = vacbot.bot.events.stats.subscribe(on_stats_event)
        await lock.wait()
        listener.unsubscribe()
    finally:
        await vacbot.after()


@cli.command(help="Get robot components life span")
@click.pass_context
@coro
async def components(ctx: click.Context) -> None:
    """Click subcommand that returns the robot's life span."""
    vacbot = CliUtil()
    try:
        await vacbot.before(ctx.obj["DEVICE"])

        lock = asyncio.Event()

        async def on_lifespan_event(event: dict) -> None:
            for key, value in event.items():
                print(f"{key}: {value}%")
            lock.set()

        lock.clear()
        listener = vacbot.bot.events.lifespan.subscribe(on_lifespan_event)
        await lock.wait()
        listener.unsubscribe()
    finally:
        await vacbot.after()


@cli.command(name="getrooms", help="Get saved rooms")
@click.pass_context
@coro
async def get_rooms(ctx: click.Context) -> None:
    """Click subcommand that returns saved room."""
    vacbot = CliUtil()
    try:
        await vacbot.before(ctx.obj["DEVICE"])

        lock = asyncio.Event()

        async def on_rooms(event: RoomsEvent) -> None:
            for room in event.rooms:
                print(f"{room.id} {room.subtype}")
            lock.set()

        lock.set()
        listener = vacbot.bot.map.events.rooms.subscribe(on_rooms)
        await lock.wait()
        listener.unsubscribe()
    finally:
        await vacbot.after()


@cli.command(
    name="exportlivemap",
    help='Get robot map and save it [filepath ex: "/folder/livemap.png"',
)
@click.argument("filepath", type=click.STRING, required=True)
@click.option(
    "--force-extension/--no-force-extension",
    default=False,
    help="Do not check if the file extension is valid.",
)
@click.pass_context
@coro
async def export_live_map(
    ctx: click.Context, filepath: str, force_extension: bool
) -> None:
    """Click subcommand that returns the live map."""
    if not force_extension and mimetypes.guess_type(filepath)[0] != "image/png":
        logging.error("exportlivemap generates a png image.")
        logging.error(
            "either change your file extension to 'png' or pass '--force_extension'."
        )
        return

    vacbot = CliUtil()
    try:
        await vacbot.before(ctx.obj["DEVICE"])

        lock = asyncio.Event()

        async def on_map(_: MapEvent) -> None:
            with open(filepath, "wb") as file:
                file.write(base64.decodebytes(vacbot.bot.map.get_base64_map()))
            lock.set()

        lock.clear()
        listener = vacbot.bot.events.map.subscribe(on_map)
        await lock.wait()
        listener.unsubscribe()
    finally:
        await vacbot.after()


@cli.command(name="getdevices", help="Get Devices")
@click.option(
    "--raw-data/--no-raw-data", default=False, help="Return raw data about all devices"
)
@coro
async def get_devices(raw_data: bool) -> None:
    """Click subcommand that returns all devices."""
    vacbot = CliUtil()
    try:
        await vacbot.before()
        if raw_data:
            print(vacbot.devices)
        else:
            for idx, device in enumerate(vacbot.devices):
                print(
                    f"{idx + 1}) {device.nick} ({device.device_name}) ({device.did}) ({device.name})"
                )
    finally:
        await vacbot.after()


class CliUtil:
    """CliUtil communicates with the bot to provide self.bot."""

    def __init__(self) -> None:
        """Init CliUtil."""
        self._config = read_config()

        self._session = aiohttp.ClientSession()

        self._api = EcovacsAPI(
            self._session,
            self._config["device_id"],
            self._config["email"],
            self._config["password_hash"],
            continent=self._config["continent"],
            country=self._config["country"],
            verify_ssl=bool(self._config["verify_ssl"]),
        )

        if not config_file_exists():
            click.echo(
                f"Not logged in. Do '{os.path.basename(sys.argv[0])} createconfig' first."
            )
            sys.exit(1)

    async def before(self, match: Union[str, None] = None) -> None:
        # pylint: disable=attribute-defined-outside-init
        """Communicate with Deebot."""
        await self._api.login()

        self.devices = await self._api.get_devices()
        if match is None:
            device = self.devices[0]
        else:
            device_ = self.match_device(match)
            if device_ is None:
                logging.warning(
                    "Failed to find a device, defaulting to first item in list."
                )
                device = self.devices[0]
            else:
                device = device_

        auth = await self._api.get_request_auth()
        self.bot = VacuumBot(
            self._session,
            auth,
            device,
            continent=self._config["continent"],
            country=self._config["country"],
            verify_ssl=bool(self._config["verify_ssl"]),
        )

    async def after(self) -> None:
        """Close all connections."""
        await self._session.close()

    def match_device(self, match: str) -> Union[Vacuum, None]:
        """Match a device based on nick, device name, did or device name."""
        for device in self.devices:
            if match in [device.nick, device.device_name, device.did, device.name]:
                return device
        return None


if __name__ == "__main__":
    cli()
