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
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union

import aiohttp

try:
    import click
except ModuleNotFoundError:
    sys.exit('Dependencies missing!! Please run "pip install deebotozmo[cli]"')

from deebotozmo import create_instances
from deebotozmo.commands import Charge, Clean, PlaySound, SetFanSpeed, SetWaterInfo
from deebotozmo.commands.clean import CleanAction, CleanArea, CleanMode
from deebotozmo.events import (
    BatteryEventDto,
    CleanLogEventDto,
    FanSpeedEventDto,
    LifeSpan,
    LifeSpanEventDto,
    MapEventDto,
    RoomsEventDto,
    StatsEventDto,
    StatusEventDto,
    WaterInfoEventDto,
)
from deebotozmo.models import Configuration, DeviceInfo, VacuumState
from deebotozmo.util import md5
from deebotozmo.vacuum_bot import VacuumBot

SECTION_DEFAULT = "DEFAULT"
DEVICE = "DEVICE"


def coro(func: Callable) -> Callable:
    """Wrap around a function to run it in coroutine."""

    @wraps(func)
    def wrapper(*args: Tuple, **kwargs: Dict) -> Any:
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


def read_config() -> Mapping[str, Any]:
    """Read and parse the config file."""
    parser = configparser.ConfigParser()
    parser.read(config_file())
    return parser[SECTION_DEFAULT]


def read_config_old() -> Mapping[str, Any]:
    """Read and parser the config file for migration."""
    parser = configparser.ConfigParser()
    with open(config_file(), encoding="utf-8") as file:
        parser.read_file(itertools.chain(["[global]"], file), source=config_file())
    return parser["global"]


def write_config(config: Mapping[str, Any]) -> None:
    """Create a new config file."""
    os.makedirs(os.path.dirname(config_file()), exist_ok=True)
    parser = configparser.ConfigParser()
    parser[SECTION_DEFAULT] = config
    with open(config_file(), "w", encoding="utf-8") as file:
        parser.write(file)


@click.group(chain=True, help="")
@click.option("--debug/--no-debug", default=False)
@click.option("--device", default=None, help="Select a device.")
@click.pass_context
def cli(
    ctx: Optional[click.Context] = None,
    debug: bool = False,
    device: Optional[str] = None,
) -> None:
    """Create a click group for nesting subcommands."""
    logging.basicConfig(format="%(name)-10s %(levelname)-8s %(message)s")
    logging.root.setLevel(logging.DEBUG if debug else logging.WARNING)

    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    assert isinstance(ctx, click.Context)
    ctx.ensure_object(dict)
    ctx.obj[DEVICE] = device


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
    password_hash = md5(password)
    device_id = md5(str(time.time()))
    async with aiohttp.ClientSession() as session:
        try:
            config = Configuration(
                session,
                device_id=device_id,
                country=country_code,
                continent=continent_code,
                verify_ssl=verify_ssl,
            )
            (authenticator, _) = create_instances(config, email, password_hash)
            await authenticator.authenticate()
        except ValueError as error:
            click.echo(error.args[0])
            sys.exit(1)

    write_config(
        {
            "email": email,
            "password_hash": password_hash,
            "device_id": device_id,
            "country": country_code,
            "continent": continent_code,
            "verify_ssl": verify_ssl,
        }
    )
    click.echo("Config saved.")
    sys.exit(0)


async def run_with_login(
    context: click.Context,
    cmd: Callable,
    *,
    cmd_args: Union[list, Dict[str, Any], None] = None,
) -> None:
    """Execute a command only."""
    if cmd_args is None:
        cmd_args = {}

    util = CliUtil()
    try:
        await util.before(context.obj[DEVICE])
        if isinstance(cmd_args, list):
            await util.bot.execute_command(cmd(*cmd_args))
        else:
            await util.bot.execute_command(cmd(**cmd_args))
    finally:
        await util.after()


@cli.command(name="playsound", help="Play welcome sound")
@click.pass_context
@coro
async def play_sound(ctx: click.Context) -> None:
    """Click subcommand that runs the welcome sound."""
    await run_with_login(ctx, PlaySound)


@cli.command(help="Auto clean")
@click.pass_context
@coro
async def clean(ctx: click.Context) -> None:
    """Click subcommand that runs the auto clean command."""
    await run_with_login(ctx, Clean, cmd_args=[CleanAction.START])


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
        ctx,
        CleanArea,
        cmd_args={"mode": CleanMode.CUSTOM_AREA, "area": area, "cleanings": cleanings},
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
        ctx,
        CleanArea,
        cmd_args={"mode": CleanMode.SPOT_AREA, "area": rooms, "cleanings": cleanings},
    )


@cli.command(name="setfanspeed", help="Set Clean Speed")
@click.argument("speed", type=click.STRING, required=True)
@click.pass_context
@coro
async def set_fan_speed(ctx: click.Context, speed: str) -> None:
    """Click subcommand that sets the fan speed."""
    await run_with_login(ctx, SetFanSpeed, cmd_args=[speed])


@cli.command(name="setwaterlevel", help="Set Water Level")
@click.argument("level", type=click.STRING, required=True)
@click.pass_context
@coro
async def set_water_level(ctx: click.Context, level: str) -> None:
    """Click subcommmand that sets the water level."""
    await run_with_login(ctx, SetWaterInfo, cmd_args=[level])


@cli.command(help="Returns to charger")
@click.pass_context
@coro
async def charge(ctx: click.Context) -> None:
    """Click subcommand that returns to charger."""
    await run_with_login(ctx, Charge)


@cli.command(help="Pause the robot")
@click.pass_context
@coro
async def pause(ctx: click.Context) -> None:
    """Click subcommand that pauses the clean."""
    await run_with_login(ctx, Clean, cmd_args=[CleanAction.PAUSE])


@cli.command(help="Resume the robot")
@click.pass_context
@coro
async def resume(ctx: click.Context) -> None:
    """Click subcommand that resumes the clean."""
    await run_with_login(ctx, Clean, cmd_args=[CleanAction.RESUME])


@cli.command(name="getcleanlogs", help="Get Clean Logs")
@click.pass_context
@coro
async def get_clean_logs(ctx: click.Context) -> None:
    """Click subcommand that returns clean logs."""
    util = CliUtil()
    try:
        await util.before(ctx.obj[DEVICE])

        event = asyncio.Event()

        async def on_clean_event(clean_log_event: CleanLogEventDto) -> None:
            print(json.dumps(asdict(clean_log_event)))
            event.set()

        listener = util.bot.events.subscribe(CleanLogEventDto, on_clean_event)
        await event.wait()
        listener.unsubscribe()
    finally:
        await util.after()


@cli.command(help="Get robot statuses [Status,Battery,FanSpeed,WaterLevel]")
@click.pass_context
@coro
async def statuses(ctx: click.Context) -> None:
    """Click subcommand that returns the robot status."""
    util = CliUtil()
    try:
        await util.before(ctx.obj[DEVICE])
        event = asyncio.Event()

        async def on_status(status_event: StatusEventDto) -> None:
            print(f"Vacuum Available: {status_event.available}")
            if isinstance(status_event.state, VacuumState):
                print(f"Vacuum State: {status_event.state.name}")
            event.set()

        status_listener = util.bot.events.subscribe(StatusEventDto, on_status)
        await event.wait()
        status_listener.unsubscribe()

        async def on_battery(battery_event: BatteryEventDto) -> None:
            print(f"Battery: {battery_event.value}%")
            event.set()

        event.clear()
        battery_listener = util.bot.events.subscribe(BatteryEventDto, on_battery)
        await event.wait()
        battery_listener.unsubscribe()

        async def on_fan_event(fan_speed_event: FanSpeedEventDto) -> None:
            print(f"Fan Speed: {fan_speed_event.speed}")
            event.set()

        event.clear()
        fan_speed_listener = util.bot.events.subscribe(FanSpeedEventDto, on_fan_event)
        await event.wait()
        fan_speed_listener.unsubscribe()

        async def on_water_level(water_info_event: WaterInfoEventDto) -> None:
            print(f"Water Level: {water_info_event.amount}")
            event.set()

        event.clear()
        water_level_listener = util.bot.events.subscribe(
            WaterInfoEventDto, on_water_level
        )
        await event.wait()
        water_level_listener.unsubscribe()
    finally:
        await util.after()


@cli.command(help="Get stats")
@click.pass_context
@coro
async def stats(ctx: click.Context) -> None:
    """Click subcommand that returns bot stats."""
    util = CliUtil()
    try:
        await util.before(ctx.obj[DEVICE])

        event = asyncio.Event()

        async def on_stats_event(stats_event: StatsEventDto) -> None:
            print(f"Stats Cid: {stats_event.clean_id}")
            print(f"Stats Area: {stats_event.area}")
            if isinstance(stats_event.time, int):
                print(f"Stats Time: {stats_event.time / 60} minutes")
            print(f"Stats Type: {stats_event.type}")
            event.set()

        listener = util.bot.events.subscribe(StatsEventDto, on_stats_event)
        await event.wait()
        listener.unsubscribe()
    finally:
        await util.after()


@cli.command(help="Get robot components life span")
@click.pass_context
@coro
async def components(ctx: click.Context) -> None:
    """Click subcommand that returns the robot's life span."""
    util = CliUtil()
    try:
        await util.before(ctx.obj[DEVICE])

        events = {
            LifeSpan.BRUSH: asyncio.Event(),
            LifeSpan.SIDE_BRUSH: asyncio.Event(),
            LifeSpan.FILTER: asyncio.Event(),
        }

        async def on_lifespan_event(lifespan_event: LifeSpanEventDto) -> None:
            print(f"{lifespan_event.type.value}: {lifespan_event.percent}%")
            events[lifespan_event.type].set()

        listener = util.bot.events.subscribe(LifeSpanEventDto, on_lifespan_event)
        for event in events.values():
            await event.wait()
        listener.unsubscribe()
    finally:
        await util.after()


@cli.command(name="getrooms", help="Get saved rooms")
@click.pass_context
@coro
async def get_rooms(ctx: click.Context) -> None:
    """Click subcommand that returns saved room."""
    util = CliUtil()
    try:
        await util.before(ctx.obj[DEVICE])

        event = asyncio.Event()

        async def on_rooms(rooms_event: RoomsEventDto) -> None:
            for room in rooms_event.rooms:
                print(f"{room.id} {room.subtype}")
            event.set()

        listener = util.bot.events.subscribe(RoomsEventDto, on_rooms)
        await event.wait()
        listener.unsubscribe()
    finally:
        await util.after()


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

    util = CliUtil()
    try:
        await util.before(ctx.obj[DEVICE])

        event = asyncio.Event()

        async def on_map(_: MapEventDto) -> None:
            with open(filepath, "wb") as file:
                file.write(base64.decodebytes(util.bot.map.get_base64_map()))
            event.set()

        listener = util.bot.events.subscribe(MapEventDto, on_map)
        await event.wait()
        listener.unsubscribe()
    finally:
        await util.after()


@cli.command(name="getdevices", help="Get Devices")
@coro
async def get_devices() -> None:
    """Click subcommand that returns all devices."""
    util = CliUtil()
    try:
        await util.before()

        for device in util.devices:
            name = device.nick
            if not name:
                name = device.name
            print(f"{name} ({device.device_name}) ({device.did})")
    finally:
        await util.after()


class CliUtil:
    """CliUtil communicates with the bot to provide self.bot."""

    def __init__(self) -> None:
        """Init CliUtil."""
        self._bot: Optional[VacuumBot] = None
        self.devices: List[DeviceInfo] = []

        try:
            config = read_config()
        except configparser.MissingSectionHeaderError:
            config = read_config_old()
            write_config(config)

        self._continent = config["continent"]
        self._country = config["country"]
        self._verify_ssl = config["verify_ssl"]

        self._session = aiohttp.ClientSession()

        _config = Configuration(
            aiohttp.ClientSession(),
            device_id=config["device_id"],
            country=config["country"],
            continent=config["continent"],
            verify_ssl=config["verify_ssl"],
        )

        (self._authenticator, self._api_client) = create_instances(
            _config, config["email"], config["password_hash"]
        )

        if not config_file_exists():
            click.echo(
                f"Not logged in. Do '{os.path.basename(sys.argv[0])} createconfig' first."
            )
            sys.exit(1)

    @property
    def bot(self) -> VacuumBot:
        """Return the vacuum bot."""
        if self._bot is None:
            click.echo("Bot can only called after calling 'before'!")
            sys.exit(1)
        return self._bot

    async def before(self, selected_device: Optional[str] = None) -> None:
        """Communicate with Deebot."""
        self.devices = await self._api_client.get_devices()
        device = self._get_matched_device(selected_device)

        self._bot = VacuumBot(self._session, device, self._api_client)

    async def after(self) -> None:
        """Close all connections."""
        await self._session.close()

    def _get_matched_device(self, device_match: Optional[str]) -> DeviceInfo:
        """Match a device based on nick, device name, did or device name or return first device."""
        if device_match is None:
            return self.devices[0]

        for device in self.devices:
            if device_match in [
                device.nick,
                device.device_name,
                device.did,
                device.name,
            ]:
                return device
        logging.warning("Failed to find a device, defaulting to first item in list.")
        return self.devices[0]
