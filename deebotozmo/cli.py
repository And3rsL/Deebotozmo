import configparser
import itertools
import os
import platform
import random
import re
import base64
import lzma
import json

import click
from pycountry_convert import country_alpha2_to_continent_code
from deebotozmo import *

_LOGGER = logging.getLogger(__name__)
vacbot = None

def config_file():
    if platform.system() == 'Windows':
        return os.path.join(os.getenv('APPDATA'), 'deebotozmo.conf')
    else:
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


def current_country():
    try:
        return requests.get('http://ipinfo.io/json').json()['country'].lower()
    except:
        return 'us'


def continent_for_country(country_code):
    return country_alpha2_to_continent_code(country_code.upper()).lower()

@click.group(chain=True)
@click.option('--debug/--no-debug', default=False)
def cli(debug):
    logging.basicConfig(format='%(name)-10s %(levelname)-8s %(message)s')
    _LOGGER.parent.setLevel(logging.DEBUG if debug else logging.ERROR)


@cli.command(help='logs in with specified email; run this first')
@click.option('--email', prompt='Ecovacs app email')
@click.option('--password', prompt='Ecovacs app password', hide_input=True)
@click.option('--country-code', prompt='your two-letter country code', default=lambda: current_country())
@click.option('--continent-code', prompt='your two-letter continent code',
              default=lambda: continent_for_country(click.get_current_context().params['country_code']))
@click.option('--verify-ssl', prompt='Verify SSL for API requests', default=True)
def CreateConfig(email, password, country_code, continent_code, verify_ssl):
    if config_file_exists() and not click.confirm('overwrite existing config?'):
        click.echo("Skipping setconfig.")
        exit(0)
    config = OrderedDict()
    password_hash = EcoVacsAPI.md5(password)
    device_id = EcoVacsAPI.md5(str(time.time()))
    try:
        EcoVacsAPI(device_id, email, password_hash, country_code, continent_code, verify_ssl)
    except ValueError as e:
        click.echo(e.args[0])
        exit(1)
    config['email'] = email
    config['password_hash'] = password_hash
    config['device_id'] = device_id
    config['country'] = country_code.lower()
    config['continent'] = continent_code.lower()
    config['verify_ssl'] = verify_ssl
    write_config(config)
    click.echo("Config saved.")
    exit(0)

@cli.command(help='Auto clean')
def clean():
    dologin()
    vacbot.Clean()

@cli.command(help='Cleans provided area(s), ex: "-602,1812,800,723"',context_settings={"ignore_unknown_options": True})
@click.argument('area', type=click.STRING, required=True)
@click.argument('cleanings', type=click.STRING, required=False)
def CustomArea(area, cleanings=1):
    dologin()
    vacbot.CustomArea(area, cleanings)

@cli.command(help='Cleans provided rooms(s), ex: "0,1" | Use GetRooms to see saved numbers',context_settings={"ignore_unknown_options": True})
@click.argument('rooms', type=click.STRING, required=True)
@click.argument('cleanings', type=click.STRING)
def SpotArea(rooms, cleanings=1):
    dologin()
    vacbot.SpotArea(rooms, cleanings)

@cli.command(help='Set Clean Speed')
@click.argument('speed', type=click.STRING, required=True)
def setfanspeed(speed):
    dologin()
    vacbot.SetFanSpeed(speed)

@cli.command(help='Set Water Level')
@click.argument('level', type=click.STRING, required=True)
def setwaterLevel(level):
    dologin()
    vacbot.SetWaterLevel(level)
    
@cli.command(help='Returns to charger')
def charge():
    dologin()
    vacbot.Charge()

@cli.command(help='Play welcome sound')
def playsound():
    dologin()
    vacbot.PlaySound()
	
@cli.command(help='pause the robot')
def pause():
    dologin()
    vacbot.CleanPause()

@cli.command(help='Resume the robot')
def resume():
    dologin()
    vacbot.CleanResume()

@cli.command(help='Get Clean Logs')
def getCleanLogs():
    dologin()
    vacbot.refresh_components()
    vacbot.GetCleanLogs()

    print(vacbot.lastCleanLogs)

@cli.command(help='Get robot statuses [Status,Battery,FanSpeed,WaterLevel]')
def statuses():
    dologin()
    vacbot.refresh_statuses()

    print("Vacuum Status: " + vacbot.vacuum_status)
    print("Battery: " + str(vacbot.battery_status) + '%')
    print("Fan Speed: " + vacbot.fan_speed)
    print("Water Level: " + vacbot.water_level)

@cli.command(help='Get stats')
def stats():
    dologin()
    vacbot.refresh_statuses()

    print("Stats Cid: " + vacbot.stats_cid)
    print("Stats Area: " + str(vacbot.stats_area))
    print("Stats Time: " + str(int(vacbot.stats_time/60)) + " minutes")
    print("Stats Type: " + vacbot.stats_type)

@cli.command(help='Get robot components life span')
def components():
    dologin()
    vacbot.refresh_components()

    for component in vacbot.components:
        print(component + ': ' + str(vacbot.components[component]) + '%')

@cli.command(help='Get saved rooms')
def getrooms():
    dologin()
    vacbot.refresh_statuses()

    for v in vacbot.getSavedRooms():
        print(str(v['id']) + ' ' + v['subtype'])

@cli.command(help='debug function, do not use :)')
def dodebug():
    dologin()
    vacbot.setScheduleUpdates(10)
    
@cli.command(help='Get robot map and save it [filepath ex: "/folder/livemap.png"')
@click.argument('filepath', type=click.STRING, required=True)
def exportLiveMap(filepath):
    dologin()
    vacbot.refresh_liveMap()

    with open(filepath, "wb") as fh:
        fh.write(base64.decodebytes(vacbot.live_map))

def dologin():
    global vacbot

    if not config_file_exists():
        click.echo("Not logged in. Do 'click setconfig' first.")
        exit(1)
    config = read_config()

    api = EcoVacsAPI(config['device_id'], config['email'], config['password_hash'],
                         config['country'], config['continent'], verify_ssl=config['verify_ssl'])

    vacuum = api.devices()[0]

    vacbot = VacBot(api.uid, api.REALM, api.resource, api.user_access_token, vacuum, config['continent'], True, verify_ssl=config['verify_ssl'])
        
    vacbot.connect_and_wait_until_ready()

if __name__ == '__main__':
    cli()