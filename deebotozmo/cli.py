#!/usr/bin/env python3
"""Cli module."""
import asyncio
import base64
import configparser
import itertools
import json
import logging
import os
import platform
import sys
import time
from dataclasses import asdict
from functools import wraps
from typing import Any, Callable, Tuple

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
from deebotozmo.ecovacs_mqtt import EcovacsMqtt
from deebotozmo.events import (
    BatteryEvent,
    CleanLogEvent,
    FanSpeedEvent,
    MapEvent,
    RoomsEvent,
    StatsEvent,
    WaterInfoEvent,
)
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
            file.write(key + "=" + str(config[key]) + "\n")


@click.group(chain=True)
@click.option("--debug/--no-debug", default=False)
def cli(debug: bool = False) -> None:
    """Create a click group for nesting subcommands."""
    logging.basicConfig(format="%(name)-10s %(levelname)-8s %(message)s")
    logging.root.setLevel(logging.DEBUG if debug else logging.ERROR)


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
        click.echo("Skipping setconfig.")
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


async def run_with_login(*args: Any, **kwargs: Any) -> None:
    """Execute a command only."""
    vacbot = DoLogin()
    await vacbot.run()
    await vacbot.bot.execute_command(*args, **kwargs)
    await vacbot.goodbye()


@cli.command(name="playsound", help="Play welcome sound")
@coro
async def play_sound() -> None:
    """Click subcommand that runs the welcome sound."""
    await run_with_login(PlaySound())


@cli.command(help="Auto clean")
@coro
async def clean() -> None:
    """Click subcommand that runs the auto clean command."""
    await run_with_login(CleanStart())


@cli.command(
    name="customarea",
    help='Cleans provided area(s), ex: "-602,1812,800,723"',
    context_settings={"ignore_unknown_options": True},
)
@click.argument("area", type=click.STRING, required=True)
@click.argument("cleanings", type=click.INT, required=False)
@coro
async def custom_area(area: str, cleanings: int = 1) -> None:
    """Click subcommand that runs a clean in a custom area."""
    await run_with_login(CleanCustomArea(map_position=area, cleanings=cleanings))


@cli.command(
    name="spotarea",
    help='Cleans provided rooms(s), ex: "0,1" | Use GetRooms to see saved numbers',
    context_settings={"ignore_unknown_options": True},
)
@click.argument("rooms", type=click.STRING, required=True)
@click.argument("cleanings", type=click.INT)
@coro
async def spot_area(rooms: str, cleanings: int = 1) -> None:
    """Click subcommand that runs a clean in a specific room."""
    await run_with_login(CleanSpotArea(area=rooms, cleanings=cleanings))


@cli.command(name="setfanspeed", help="Set Clean Speed")
@click.argument("speed", type=click.STRING, required=True)
@coro
async def set_fan_speed(speed: str) -> None:
    """Click subcommand that sets the fan speed."""
    await run_with_login(SetFanSpeed(speed))


@cli.command(name="setwaterlevel", help="Set Water Level")
@click.argument("level", type=click.STRING, required=True)
@coro
async def set_water_level(level: str) -> None:
    """Click subcommmand that sets the water level."""
    await run_with_login(SetWaterLevel(level))


@cli.command(help="Returns to charger")
@coro
async def charge() -> None:
    """Click subcommand that returns to charger."""
    await run_with_login(Charge())


@cli.command(help="Pause the robot")
@coro
async def pause() -> None:
    """Click subcommand that pauses the clean."""
    await run_with_login(CleanPause())


@cli.command(help="Resume the robot")
@coro
async def resume() -> None:
    """Click subcommand that resumes the clean."""
    await run_with_login(CleanResume())


@cli.command(name="getcleanlogs", help="Get Clean Logs")
@coro
async def get_clean_logs() -> None:
    """Click subcommand that returns clean logs."""
    vacbot = DoLogin()
    await vacbot.run()

    lock = asyncio.Lock()
    await lock.acquire()

    async def on_clean_event(event: CleanLogEvent) -> None:
        print(json.dumps(asdict(event)))
        lock.release()

    listener = vacbot.bot.events.clean_logs.subscribe(on_clean_event)
    await lock.acquire()
    vacbot.bot.events.clean_logs.unsubscribe(listener)

    await vacbot.goodbye()


@cli.command(help="Get robot statuses [Status,Battery,FanSpeed,WaterLevel]")
@coro
async def statuses() -> None:
    """Click subcommand that returns the robot status."""
    vacbot = DoLogin()
    await vacbot.run()
    lock = asyncio.Lock()

    print(f"Vacuum State: {str(vacbot.bot.status.state).rsplit('.', maxsplit=1)[-1]}")

    await lock.acquire()

    async def on_battery(event: BatteryEvent) -> None:
        print("Battery: " + str(event.value) + "%")
        lock.release()

    battery_listener = vacbot.bot.events.battery.subscribe(on_battery)
    await lock.acquire()
    vacbot.bot.events.battery.unsubscribe(battery_listener)

    async def on_fan_event(event: FanSpeedEvent) -> None:
        print("Fan Speed: " + str(event.speed))
        lock.release()

    fan_speed_listener = vacbot.bot.events.fan_speed.subscribe(on_fan_event)
    await lock.acquire()
    vacbot.bot.events.fan_speed.unsubscribe(fan_speed_listener)

    async def on_water_level(event: WaterInfoEvent) -> None:
        print("Water Level: " + str(event.amount))
        lock.release()

    water_level_listener = vacbot.bot.events.water_info.subscribe(on_water_level)
    await lock.acquire()
    vacbot.bot.events.water_info.unsubscribe(water_level_listener)

    await vacbot.goodbye()


@cli.command(help="Get stats")
@coro
async def stats() -> None:
    """Click subcommand that returns bot stats."""
    vacbot = DoLogin()
    await vacbot.run()

    lock = asyncio.Lock()
    await lock.acquire()

    async def on_stats_event(event: StatsEvent) -> None:
        print("Stats Cid: " + str(event.clean_id))
        print("Stats Area: " + str(event.area))
        if isinstance(event.time, int):
            print("Stats Time: " + str(int(event.time / 60)) + " minutes")
        print("Stats Type: " + str(event.type))
        lock.release()

    listener = vacbot.bot.events.stats.subscribe(on_stats_event)
    await lock.acquire()
    vacbot.bot.events.stats.unsubscribe(listener)

    await vacbot.goodbye()


@cli.command(help="Get robot components life span")
@coro
async def components() -> None:
    """Click subcommand that returns the robot's life span."""
    vacbot = DoLogin()
    await vacbot.run()

    lock = asyncio.Lock()
    await lock.acquire()

    async def on_lifespan_event(event: dict) -> None:
        for key, value in event.items():
            print(f"{key}: {value}%")
        lock.release()

    listener = vacbot.bot.events.lifespan.subscribe(on_lifespan_event)
    await lock.acquire()
    vacbot.bot.events.lifespan.unsubscribe(listener)

    await vacbot.goodbye()


@cli.command(name="getrooms", help="Get saved rooms")
@coro
async def get_rooms() -> None:
    """Click subcommand that returns saved room."""
    vacbot = DoLogin()
    await vacbot.run()

    lock = asyncio.Lock()
    await lock.acquire()

    async def on_rooms(event: RoomsEvent) -> None:
        for room in event.rooms:
            print(str(room.id) + " " + str(room.subtype))
        lock.release()

    listener = vacbot.bot.map.events.rooms.subscribe(on_rooms)
    await lock.acquire()
    vacbot.bot.map.events.rooms.unsubscribe(listener)

    await vacbot.goodbye()


@cli.command(
    name="exportlivemap",
    help='Get robot map and save it [filepath ex: "/folder/livemap.png"',
)
@click.argument("filepath", type=click.STRING, required=True)
@coro
async def export_live_map(filepath: str) -> None:
    """Click subcommand that returns the live map."""
    vacbot = DoLogin()
    await vacbot.run()

    lock = asyncio.Lock()
    await lock.acquire()

    async def on_map(_: MapEvent) -> None:
        with open(filepath, "wb") as file:
            file.write(base64.decodebytes(vacbot.bot.map.get_base64_map()))
        lock.release()

    listener = vacbot.bot.events.map.subscribe(on_map)
    await lock.acquire()
    vacbot.bot.events.map.unsubscribe(listener)

    await vacbot.goodbye()


class DoLogin:
    """DoLogin communicates with the bot to provide self.bot."""

    def __init__(self) -> None:
        """Init DoLogin."""
        # self.session = None
        # self.auth = None
        # self.devices_ = None
        # self.bot = None
        # self.mqtt = None
        return

    async def run(self) -> None:
        # pylint: disable=attribute-defined-outside-init
        """Communicate with Deebot."""
        config = read_config()

        self.session = aiohttp.ClientSession()

        self.api = EcovacsAPI(
            self.session,
            config["device_id"],
            config["email"],
            config["password_hash"],
            continent=config["continent"],
            country=config["country"],
            verify_ssl=bool(config["verify_ssl"]),
        )

        if not config_file_exists():
            click.echo(
                "Not logged in. "
                + f"Do '{os.path.basename(sys.argv[0])} createconfig' first."
            )
            sys.exit(1)

        await self.api.login()

        self.devices_ = await self.api.get_devices()

        self.auth = await self.api.get_request_auth()
        self.bot = VacuumBot(
            self.session,
            self.auth,
            self.devices_[0],
            continent=config["continent"],
            country=config["country"],
            verify_ssl=bool(config["verify_ssl"]),
        )

        self.mqtt = EcovacsMqtt(
            self.auth,
            continent=config["continent"],
            country=config["country"],
        )
        await self.mqtt.subscribe(self.bot)

    async def goodbye(self) -> None:
        """Close all connections."""
        self.mqtt.unsubscribe(self.bot)
        await self.session.close()


if __name__ == "__main__":
    cli()
