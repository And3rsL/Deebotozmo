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

class BotWait():
    pass

    def wait(self, bot):
        raise NotImplementedError()


class TimeWait(BotWait):
    def __init__(self, seconds):
        super().__init__()
        self.seconds = seconds

    def wait(self, bot):
        click.echo("waiting for " + str(self.seconds) + "s")
        time.sleep(self.seconds)


class StatusWait(BotWait):
    def __init__(self, wait_on, wait_for):
        super().__init__()
        self.wait_on = wait_on
        self.wait_for = wait_for

    def wait(self, bot):
        if not hasattr(bot, self.wait_on):
            raise ValueError("object " + bot + " does not have method " + self.wait_on)
        _LOGGER.debug("waiting on " + self.wait_on + " for value " + self.wait_for)

        while getattr(bot, self.wait_on) != self.wait_for:
            time.sleep(0.5)
        _LOGGER.debug("wait complete; " + self.wait_on + " is now " + self.wait_for)


class CliAction:
    def __init__(self, vac_command, terminal=False, wait=None):
        self.vac_command = vac_command
        self.terminal = terminal
        self.wait = wait


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
    # noinspection PyBroadException
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
def login(email, password, country_code, continent_code, verify_ssl):
    if config_file_exists() and not click.confirm('overwrite existing config?'):
        click.echo("Skipping login.")
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


@cli.command(help='auto clean until bot returns to charger by itself')
def clean():
    waiter = StatusWait('charge_status', 'charging')    
    return CliAction('clean', {'act': 'go','type': 'auto'}, wait=waiter)

@cli.command(help='cleans provided area(s), ex: "0,1"',context_settings={"ignore_unknown_options": True}) #ignore_unknown for map coordinates with negatives
@click.option("--map-position","-p", is_flag=True, help='clean provided map position instead of area, ex: "-602,1812,800,723"')
@click.argument('area', type=click.STRING, required=True)
def area(area, map_position):
    if map_position:
        return CliAction('clean', {'act': 'start', 'content': area, 'count': 1, 'type': 'spotArea'}, wait=StatusWait('charge_status', 'returning'))    
    else:
        return CliAction('clean', {'act': 'start', 'content': area, 'count': 1, 'type': 'customArea'}, wait=StatusWait('charge_status', 'returning'))
    
@cli.command(help='Set Clean Speed')
@click.argument('speed', type=click.STRING, required=True)
def setfanspeed(speed):
    return CliAction('setSpeed', {'speed': speed}, wait=None)    
    
@cli.command(help='Returns to charger')
def charge():
    return CliAction('charge', {'act': 'go'}, wait=StatusWait('clean_status', 'working'))

@cli.command(help='Play welcome sound')
def playsound():
    return CliAction("playSound", terminal=False)

@cli.command(help='Charge State')
def chargestate():
    return CliAction("getChargeState", terminal=True, wait=StatusWait('charge_status', 'charging'))

@cli.command(help='Get Fan Speed')
def fanspeed():
    return CliAction("getSpeed", terminal=False)

@cli.command(help='Battery State')
def batterystate():
    return CliAction("getBatteryState", terminal=False)
	
@cli.command(help='pause the robot')
def pause():
    return CliAction('clean', {'act': 'pause'}, wait=StatusWait('vacuum_status', 'pause'))

@cli.command(help='resume the robot')
def resume():
    return CliAction('clean', {'act': 'resume'}, wait=StatusWait('vacuum_status', 'working'))

 #   public void UpdateMapBuffer(byte[] bArr) {
#        if (bArr != null) {
#            for (int i = 0; i < bArr.length; i++) {
#                byte[][] bArr2 = this.buffer;
#                int i2 = this.width;
#                bArr2[i / i2][i % i2] = bArr[i];
#            }
#        }
#    }

@cli.resultcallback()
def run(actions, debug):
    actions = list(filter(None.__ne__, actions))
	
	
    if not config_file_exists():
        click.echo("Not logged in. Do 'click login' first.")
        exit(1)

    if debug:
        _LOGGER.debug("will run {}".format(actions))

    if actions:
        config = read_config()
        api = EcoVacsAPI(config['device_id'], config['email'], config['password_hash'],
                         config['country'], config['continent'], verify_ssl=config['verify_ssl'])
        vacuum = api.devices()[0]
        vacbot = VacBot(api.uid, api.REALM, api.resource, api.user_access_token, vacuum, config['continent'], verify_ssl=config['verify_ssl'])
        vacbot.connect_and_wait_until_ready()

        for action in actions:
            click.echo("performing " + str(action.vac_command))
            #vacbot.SetFanSpeed('normal')
            vacbot.AddMapPiece(18, 'XQAABAAQJwAAAABv/f//o7f/Rz5IFXI5YVG4kijmo4YH+e7kHoLTL8U6PAFLrDoHiPik94CQxE6Ahy50KfRupEoM2FBfrhLa5h/0ADHOl2zb6e7oug0mqOb7m7WnRnzpSqxWYA==')
            vacbot.AddMapPiece(19, 'XQAABAAQJwAAAABv/f//o7f/Rz5IFXI5YVG4kijmo4YH+e7kHoLTL8U6PAFKxyhHay2Dza11Ph3qRJQ570U1QJDo6TWJHYKGopgVK8vBIgeNsCJHrrwwbM0YYRreYpDYiFhEwTtRDAz2VXwkMa+vbBj5s1a3ZHnBKalOcYsQT0hK0dn5ALWjx18yEsYFCMhZ/jitw3hzd7CxdUdhv6kjA1l53vW3mPGBgTxv/GYEcPth17pcbS9+0TYb/ZifOVG73MOIZ8m1ePntACu5qQ==')
            vacbot.AddMapPiece(20, 'XQAABAAQJwAAAABv/f//o7f/Rz5IFXI5YVG4kijmo4YH+e7kHoLTL8U6PAFLqGTV7wMaAE+Rnbna6pQxJtBBVHpTtu+J2J1VlyNn9KOlQtSGjKPgkLfNDR1ACj+3JveXCLLcJZQmyHzWTx3Uno9DxRYrvEf72uc6auTl2dclqK28Gv28TBXUfg0zaV/S6MWaQ0Vsu4/t7gEvhyxCRJNdWi4BkDvVJ9hGS/lYFWjv/9k1ETMiRkDFv7p7Wbu8yX+bxNiNWOJuap+EwXDNkutdJ+W8VHYyQ8frtMOdebVgOuixevJH21JoQ300rt0AjfiyEJAFLuyFOSgoy7XJjZC5vqOL8edoscWw+/oOUxJ+JRhmIQXl5n7PHBevLvYC1UYbIqpSaYY2sJ+bbNC9T3TYz9c+0Sr+rr9ta9DvuJB45fLXB1uz1QAtQxFS0wT5rq5Yu7/Wr7fFQTZsAA==')
            vacbot.AddMapPiece(21, 'XQAABAAQJwAAAABv/f//o7f/Rz5IFXI5YVG4kijmo4YH+e7kHoLTL8U6PAFLrgRNnXqlc8O+4Fh7lJq+Ma+LFL0vg6sb4P9hAA==')
            vacbot.AddMapPiece(26, 'XQAABAAQJwAAAABumEeZGKjVsmmCO/kC5Z7SSyjPkVmdC5E8QMAB41bwMnNF99+FfxhGUcnD9iY3tsJffXvOJh9QaJAeFejdaaeIRiWc3Qx2O5uR4OHn5N3pS0Kk5CrATjMhF2ZjGXVwo8JWSBK9AIAGeZs8tsO9xh4ucuOhGH4wI7M+MsYFi3boSMt5MAN0eZxTk2xa6n4epM3htfiSSJd1s+nrs4pqxHGeb6826jFbCJvvVByOiNwjXej+dtTWXc9dhM/V/JQI8Cex3tHvGzw1QP9J/wS0TTLwbQHJn8LTWE6xOXOuA7n4glttr0m17Y1Qo/5YXYbwxAmW47UhXhID5gA=')
            vacbot.AddMapPiece(27, 'XQAABAAQJwAAAADuiEfQeQRdtrRSvel/f9de/jaab2xqyvBP5zEyIkZBTEhglrZmtwh0JQllPjUhYW2weqSofRxchnwN9Wcdqt3SUAQWENK2seXnyICG8Ou1BNUSzjGqyn1G2FBwgOYRhMZXX6ZsGb0l87rMUtRrQ2qzv62T1HwbtXju/hB8ueNGQyRsa1EGTw2eGI6ArrT6sKKcLYKTOuhRL02uH2sqQiFMVgdFTiZZ+9b1MFqV46CsZczgFG+8SOdHgMeVa2tYq/zKGjrh7XEk3aqMxqRqm9vHhycOPzCokQ+OJN4kmVYa2v8mSPPGfo6/XV96BsDoOJwvYHA/ZpuyncxzC8phpDQdlQsSUa6jdZkARc8ciLFVclk5tWn0ODqezxVNq13scssj2iuYveiqg25SWPGQshh4zPgOPRuAdcpgIjxaQ5clQjt84wH6v4LgM/doBDEdOEoJM/eOjMLvXfuxXXYHVQlDe6exnAsMc7yUL1U6Co+nZ72xXo+T3bERgLIoU09fudf0nzf7pR5jy+1j2CDMI6GZGyyBSQIOfLsuqcZuDI5X2kIMKXyM5SWwEQLOa2HO0780EZHN8ri/+yCDHYeakCmEoW4TmKYcdMsMf/agwXLErTtfTn3GF4V3ipzeeAA=')
            vacbot.AddMapPiece(28, 'XQAABAAQJwAAAACAnOoM3MkOb8W/+7Hpax9BV8gqzECGCB3b9yYAnpvNdCptL8jsPBJfc5vYEeIKj0ntQ/0pPjS7AhQX1qmNoz02uEiIXma5KTsMCo3X2lbYCUypcE3GVYSh5+2+HQdfKewyxknpt6jSDaNQcvBZscKu6TyrP8q05QfAERaZyT4u1gRecqEqAfbRge393BM5bOn/nelKkl/aFPABR9VbbESLawmQCJu5YsdGodDKdVLbIW/WDvz0wFiMGw9NkPMh7AnoO8JVS1SZtf0J81qmjn3Jvh0y7VpFUilyskFM465hU6ZNWFlrJOfaOynKYpIgOgkX7Wcs8Q4OjFzUwSEMkEYqd7sGN+HHm/pVICq77BuOmm1uFSD075M5UZ4mKN7Hsry5h/FNybQi5Uk+qThbRn71NRIvzZ9apVycmpwU6Qu8Bh4evMzrn0teJGYkSlzDAilHxMSjvHJBJzrY9jBLZHndpQfpW15G2hTLs/WMpsTc7mLK0v6VXmNv4NJ+xLuVSgrd9KjpLeQK+czn+OmypBayGHRooYkNvkynsCQk9TZaI/zS8noj9l3sMDS1fOILQs35IRux5zdkrASd70L9fPYir3OcMYLFE3c4KfVajSWU+DJGsep2WszmGaNobgpuSbUbrUYUGh4SQWnxLsuc02VFsQ2zqDzqjkqa0H8DvbYGdKfWQ112D0e7DAkUVTz+d84tEUhqxG39kwtTfIZLejze3gA=')
            vacbot.AddMapPiece(29, 'XQAABAAQJwAAAAEAPHOs6RjZq++b/qRoyIgEl2h2eVTCLE/IiTgTKZ7q3Uq77LgMSnd+MBqa+nKQFrYGs7FVVbx+sXF0sAqMs7vinPf7y3V+84j06HxVYV3x1eLt4mbwlNz9wLUALijbgT1Vbh40mkGBgazva/fnuCkee5HK4+3v+/V/3PjkSMdxq++/0H4D2RVcbuxAi5DQH4UXBsGBEr4PMNSbAA==')
            vacbot.AddMapPiece(34, 'XQAABAAQJwAAAABuekgP+OTPEa+tLdn9c23nlgoOoqIsfuzSV+JqPT2r3+BPZJeoShXkVk+KUkmnnG1oNh+uo2qNMEa85iOUQ4ppg0cnbwMaIl0wR3rkIu4F7l9K6vsPL1xu2pa4LF3BOr7n73N9kb/W4SDDOGMp+mOZN9sefg7aAF2LhlZpR5AHjgA=')
            vacbot.AddMapPiece(35, 'XQAABAAQJwAAAADv+///o7daD4AonX0IU+kVVK4GpV52Wa3CaqAQ1Zp8lKuInxGfsZ0SgiQSSt/D5OqC+PEFbEAnACX1wxbpFudnJlGTMHkkl0/UxpPSAQRDwsqPbPRV+FgwU+4Mo/ySuHFNSezga5ZkjrQlzr2sFKEscqZMPspKDVeooEKTQuQ2xEu4A+RbwDH4JLLYga49y0wP2fwRWQXZg7QTTXrhxX2E/+2E6rjYzECdP3ThACTT6Z3jld303DOfDceNLBoCtarVA3rSpHO4HXbDuaCBde7ubzWshpcOFVO+AuGCq58FPTMsxT97iKoTjcLXKqbUICA=')
            vacbot.AddMapPiece(36, 'XQAABAAQJwAAAADn/RP9T4N/GE4i7lBHZ4fhw+Hs1Vc/5/TskM9BzJxrPJdPyn63gX1mYExNzGBkFb3YCBc3bn+uoNAQ3iY1aW0G+v1z0FsWeQq5JKacpAYWsi69i4VTYMTCMno4IoQCjZH7xsLIiWH+W1TcxuGfXgRFDVZe+pJiD6XcZXL2FwLzWlS6LIs8Fm71bHzlJA4XXJLXRSIR6RGvKlaVX7REjLmSgU98dmnkHyi/LBr92jHlVnvQLukXVERfdjC3Vnmiw2mZhNKaEyXKpqljb/tE2Tw0uxt2pXCWu1H7AnnzubiDaL5lU6tBb8cnJr2aRJvBl5ssG2vDcezEcm6U7glILTlOHULjnyDH8tk0WzPyEv21PObZwVYLTY6pneV0fIwGFjqdz1i/foQluF0qDX4OG2RFfT+UYg+mIA5qSRNg0ABAGZ8nWmWfTRb0RLkvNEbdekLWIWQfGG7YzpQFXQE+x++s7/yT73aEW2OEP/X0rKIsye8JDeMqVKFP3nXJc5DVVEvCOPE/xGwfbG2Pu/xpPgc3XGYv6TEKe1HAlGdMoPhxYzYnFNIDs5SI5f5aI+blA6tsTez9gfc4OvVK0kgUexzq3SMk46X7GS8p8DLBu/2r/npHX95UPsmRA/pQ2AT80b0tZZwk4hY=')
            vacbot.StampMap()
            #vacbot.request_all_statuses()
            #action.wait.wait(vacbot)
        vacbot.disconnect(wait=True)
		
        for v in vacbot.rooms:
            _LOGGER.debug(v)

        _LOGGER.debug("Battery Status: {}".format(vacbot.battery_status))
        _LOGGER.debug("Vacuum Status: {}".format(vacbot.vacuum_status))
        _LOGGER.debug("Fan Speed: {}".format(vacbot.fan_speed))
        _LOGGER.debug("Image Url: {}".format(vacbot.last_clean_image))

    click.echo("done")


if __name__ == '__main__':
    cli()
