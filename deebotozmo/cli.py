#!/usr/bin/env python3

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

import aiohttp
import click

from deebotozmo.commands import (Charge, CleanCustomArea, CleanPause,
                                 CleanResume, CleanSpotArea, CleanStart,
                                 PlaySound, SetFanSpeed, SetWaterLevel)
from deebotozmo.ecovacs_api import EcovacsAPI
from deebotozmo.ecovacs_mqtt import EcovacsMqtt
from deebotozmo.events import (BatteryEvent, CleanLogEvent, FanSpeedEvent,
                               LifeSpanEvent, MapEvent, RoomsEvent, StatsEvent,
                               WaterInfoEvent)
from deebotozmo.util import md5
from deebotozmo.vacuum_bot import VacuumBot

_LOGGER = logging.getLogger(__name__)

def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(f(*args, **kwargs))
    return wrapper

def config_file():
    if platform.system() == 'Windows':
        return os.path.join(os.getenv('APPDATA'), 'deebotozmo.conf')
    return os.path.expanduser('~/.config/deebotozmo.conf')


def config_file_exists():
    return os.path.isfile(config_file())


def read_config():
    parser = configparser.ConfigParser()
    with open(config_file()) as fp:
        parser.read_file(itertools.chain(['[global]'], fp), source=config_file())
    return parser['global']


def write_config(config):
    os.makedirs(os.path.dirname(config_file()), exist_ok=True)
    with open(config_file(), 'w') as fp:
        for key in config:
            fp.write(key + '=' + str(config[key]) + "\n")


@click.group(chain=True)
@click.option('--debug/--no-debug', default=False)
def cli(debug):
    logging.basicConfig(format='%(name)-10s %(levelname)-8s %(message)s')
    _LOGGER.parent.setLevel(logging.DEBUG if debug else logging.ERROR)


@cli.command(help='logs in with specified email; run this first')
@click.option('--email', prompt='Ecovacs app email')
@click.option('--password', prompt='Ecovacs app password', hide_input=True)
@click.option('--country-code', prompt='your two-letter country code')
@click.option('--continent-code', prompt='your two-letter continent code')
@click.option('--verify-ssl', prompt='Verify SSL for API requests', default=True)
@coro
async def CreateConfig(email, password, country_code, continent_code, verify_ssl):
    if config_file_exists() and not click.confirm('overwrite existing config?'):
        click.echo("Skipping setconfig.")
        sys.exit(0)
    config = {}
    password_hash = md5(password)
    device_id = md5(str(time.time()))
    async with aiohttp.ClientSession() as session:
        try:
            EcovacsAPI(session, device_id, email, password_hash, continent=continent_code,
                       country=country_code, verify_ssl=verify_ssl)
        except ValueError as e:
            click.echo(e.args[0])
            sys.exit(1)
    config['email'] = email
    config['password_hash'] = password_hash
    config['device_id'] = device_id
    config['country'] = country_code.lower()
    config['continent'] = continent_code.lower()
    config['verify_ssl'] = verify_ssl
    write_config(config)
    click.echo("Config saved.")
    sys.exit(0)

async def run_with_login(*args, **kwargs):
    vacbot = DoLogin()
    await vacbot.run()
    await vacbot.bot.execute_command(*args, **kwargs)
    await vacbot.goodbye()

@cli.command(help='Play welcome sound')
@coro
async def playsound():
    await run_with_login(PlaySound())

@cli.command(help='Auto clean')
@coro
async def clean():
    await run_with_login(CleanStart())

@cli.command(help='Cleans provided area(s), ex: "-602,1812,800,723"', context_settings={"ignore_unknown_options": True})
@click.argument('area', type=click.STRING, required=True)
@click.argument('cleanings', type=click.STRING, required=False)
@coro
async def CustomArea(area, cleanings=1):
    await run_with_login(CleanCustomArea(map_position=area, cleanings=cleanings))

@cli.command(help='Cleans provided rooms(s), ex: "0,1" | Use GetRooms to see saved numbers',
             context_settings={"ignore_unknown_options": True})
@click.argument('rooms', type=click.STRING, required=True)
@click.argument('cleanings', type=click.STRING)
@coro
async def SpotArea(rooms, cleanings=1):
    await run_with_login(CleanSpotArea(area=rooms, cleanings=cleanings))

@cli.command(help='Set Clean Speed')
@click.argument('speed', type=click.STRING, required=True)
@coro
async def setfanspeed(speed):
    await run_with_login(SetFanSpeed(speed))

@cli.command(help='Set Water Level')
@click.argument('level', type=click.STRING, required=True)
@coro
async def setwaterLevel(level):
    await run_with_login(SetWaterLevel(level))

@cli.command(help='Returns to charger')
@coro
async def charge():
    await run_with_login(Charge())

@cli.command(help='Pause the robot')
@coro
async def pause():
    await run_with_login(CleanPause())

@cli.command(help='Resume the robot')
@coro
async def resume():
    await run_with_login(CleanResume())

@cli.command(help='Get Clean Logs')
@coro
async def getCleanLogs():
    vacbot = DoLogin()
    await vacbot.run()

    lock = asyncio.Lock()
    await lock.acquire()
    async def on_clean_event(event: CleanLogEvent):
        print(json.dumps(asdict(event)))
        lock.release()

    listener = vacbot.bot.cleanLogsEvents.subscribe(on_clean_event)
    await lock.acquire()
    vacbot.bot.cleanLogsEvents.unsubscribe(listener)

    await vacbot.goodbye()

@cli.command(help='Get robot statuses [Status,Battery,FanSpeed,WaterLevel]')
@coro
async def statuses():
    vacbot = DoLogin()
    await vacbot.run()
    lock = asyncio.Lock()

    print ("Vacuum State: " + str(vacbot.bot.status.state).split(".")[-1])

    await lock.acquire()
    async def on_battery(event: BatteryEvent):
        print("Battery: " + str(event.value) + "%")
        lock.release()
    listener = vacbot.bot.batteryEvents.subscribe(on_battery)
    await lock.acquire()
    vacbot.bot.batteryEvents.unsubscribe(listener)

    async def on_fan_event(event: FanSpeedEvent):
        print("Fan Speed: " + str(event.speed))
        lock.release()
    listener = vacbot.bot.fanSpeedEvents.subscribe(on_fan_event)
    await lock.acquire()
    vacbot.bot.fanSpeedEvents.unsubscribe(listener)

    async def on_water_level(event: WaterInfoEvent):
        print("Water Level: " + str(event.amount))
        lock.release()
    listener = vacbot.bot.waterEvents.subscribe(on_water_level)
    await lock.acquire()
    vacbot.bot.waterEvents.unsubscribe(listener)

    await vacbot.goodbye()

@cli.command(help='Get stats')
@coro
async def stats():
    vacbot = DoLogin()
    await vacbot.run()

    lock = asyncio.Lock()
    await lock.acquire()
    async def on_stats_event(event: StatsEvent):
        print("Stats Cid: " + str(event.clean_id))
        print("Stats Area: " + str(event.area))
        print("Stats Time: " + str(int(event.time / 60)) + " minutes")
        print("Stats Type: " + str(event.type))
        lock.release()
    listener = vacbot.bot.statsEvents.subscribe(on_stats_event)
    await lock.acquire()
    vacbot.bot.statsEvents.unsubscribe(listener)

    await vacbot.goodbye()

# Needs a lock but the lifespan event is emitted
# for every component, so it wouldn't work
@cli.command(help='Get robot components life span')
@coro
async def components():
    vacbot = DoLogin()
    await vacbot.run()

    async def on_lifespan_event(event: LifeSpanEvent):
        print(str(event.type) + ": " + str(event.percent) + "%")
    listener = vacbot.bot.lifespanEvents.subscribe(on_lifespan_event)
    vacbot.bot.lifespanEvents.unsubscribe(listener)

    await vacbot.goodbye()

@cli.command(help='Get saved rooms')
@coro
async def getrooms():
    vacbot = DoLogin()
    await vacbot.run()

    lock = asyncio.Lock()
    await lock.acquire()
    async def on_rooms(event: RoomsEvent):
        for v in event.rooms:
            print(str(v.id) + " " + str(v.subtype))
        lock.release()
    listener = vacbot.bot.map.roomsEvents.subscribe(on_rooms)
    await lock.acquire()
    vacbot.bot.map.roomsEvents.unsubscribe(listener)

    await vacbot.goodbye()

@cli.command(help='Get robot map and save it [filepath ex: "/folder/livemap.png"')
@click.argument('filepath', type=click.STRING, required=True)
@coro
async def exportLiveMap(filepath):
    vacbot = DoLogin()
    await vacbot.run()

    lock = asyncio.Lock()
    await lock.acquire()
    async def on_map(_: MapEvent):
        with open(filepath, "wb") as fh:
            fh.write(base64.decodebytes(vacbot.bot.map.get_base64_map()))
        lock.release()
    listener = vacbot.bot.map.mapEvents.subscribe(on_map)
    await lock.acquire()
    vacbot.bot.map.mapEvents.unsubscribe(listener)

    await vacbot.goodbye()

class DoLogin:
    def __init__(self):
        return

    async def run(self):
        if not config_file_exists():
            click.echo("Not logged in. Do '%s createconfig' first." % (os.path.basename(sys.argv[0]),))
            sys.exit(1)

        config = read_config()

        self.session = aiohttp.ClientSession()

        self.api = EcovacsAPI(self.session, config['device_id'], config['email'], config['password_hash'],
                                    continent=config['continent'], country=config['country'],
                                    verify_ssl=bool(config['verify_ssl']))
        await self.api.login()

        self.devices_ = await self.api.get_devices()

        self.auth = await self.api.get_request_auth()
        self.bot = VacuumBot(self.session, self.auth, self.devices_[0], continent=config['continent'],
                                   country=config['country'], verify_ssl=bool(config['verify_ssl']))

        self.mqtt = EcovacsMqtt(self.auth, continent=config['continent'], country=config['country'])
        await self.mqtt.subscribe(self.bot)

    async def goodbye(self):
        self.mqtt.unsubscribe(self.bot)
        await self.session.close()

if __name__ == '__main__':
    cli()
