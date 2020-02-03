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


class FrequencyParamType(click.ParamType):
    name = 'frequency'
    RATIONAL_PATTERN = re.compile(r'([.0-9]+)/([.0-9]+)')

    def convert(self, value, param, ctx):
        result = None
        try:
            search = self.RATIONAL_PATTERN.search(value)
            if search:
                result = float(search.group(1)) / float(search.group(2))
            else:
                try:
                    result = float(value)
                except ValueError:
                    pass
        except (ValueError, ArithmeticError):
            pass

        if result is None:
            self.fail('%s is not a valid frequency' % value, param, ctx)
        if 0 <= result <= 1:
            return result

        self.fail('%s is not between 0 and 1' % value, param, ctx)


FREQUENCY = FrequencyParamType()


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


def should_run(frequency):
    if frequency is None:
        return True
    n = random.random()
    result = n <= frequency
    _LOGGER.debug("tossing coin: {:0.3f} <= {:0.3f}: {}".format(n, frequency, result))
    return result


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
    return CliAction('setSpeed', {'speed': speed}, terminal=False)    
    
@cli.command(help='Returns to charger')
def charge():
    return CliAction('charge', {'act': 'go'}, terminal=False, wait=StatusWait('clean_status', 'working'))

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
    return CliAction('clean', {'act': 'pause'}, terminal=True, wait=StatusWait('vacuum_status', 'pause'))

@cli.command(help='resume the robot')
def resume():
    return CliAction('clean', {'act': 'resume'}, terminal=True, wait=StatusWait('vacuum_status', 'working'))

@cli.command(help='test')
def test():
    # Get lzma output size (as done by the Android app)
    b64 = 'XQAABADoAwAAACe/wY/wAXMtXB0BRTG11RZpNoaJR3MvphcOqp7H+VtmwqLso+xJ2eOQbM2BbszF/pf0VLYbvS322TQoShcj+T1BzPcmRuNKAMD0nAnkVFFpla5ipwEkkUmVAeGeJjf1PdlnmizSbezkr4XlZQ/1WD2INmfUaWwr1Q6lyOih3j8bgMiPPvmpHpTPaf3vAOLUOMcn26qq09zKDzN/lmJyzA40tdtbLYKV6Mbj+sAjfWxqjYcqn55Hst5mflAY4c11DWkuDX+72WXuyAp8CsDQ5UdSLroZyuJgVg4Y8V9l+hNiwmYr+EFt4GJL+0InTF2V38EMLWq5yYHiBtuXJNOEct6RPPloVVIARyJr1s8/LC36KlOCEz65Owl9bNlzV2WF1WrnSwXiLAJTt7F3owFcRYVuL98RJHXrDRLhQfrYZgJALVL1QXrCbXS+2sYx6itLUoQ6lUUQlvt68zTXhdCEzTPWyzVddWd6ntogUlyNq8ZnKUpa2RU0G5MIaG1OOIi6saBcmHn45TyR0TGsPsfYiXCTctFMoCavQzwoGurEtqNgNlVv1nFiFyVRw9EJrgExVH5qQplQjCZt3HJZPrD4+7UfIX21rzsgcy/Fv+Lr3YkFfdbQLlYi213TjVGS+HhHRZ1E/Dcc5dvO4fwn9N8V0JcYKo3c/BgrLcti9KAPfwOMRvnMI4yFQWcU1AxkjgwBZzf8Qbtj5sWDzrxz+Ki1NIJRHv/pBJSRxzJBdsmMtfvfce1EGet8GjkCJFKh22mP48Hdvh9nlrUEY9rnFVy5Ow2PFrRIxA1XmWupmcFLXDU='
    b64 = b64[0].upper() + b64[1:]
    data = base64.b64decode(b64)
    _LOGGER.debug(data)
    len_array = data[5:5+4]
    len_value = ((len_array[0] & 0xFF) | (len_array[1] << 8 & 0xFF00) | (len_array[2] << 16 & 0xFF0000) | (len_array[3] << 24 & 0xFF000000)) 

    # Init the LZMA decompressor using the lzma header
    dec = lzma.LZMADecompressor(lzma.FORMAT_RAW, None, [lzma._decode_filter_properties(lzma.FILTER_LZMA1, data[0:5])])
        
    # Decompress the lzma stream to get raw data
    val = dec.decompress(data[9:], len_value)
    base64EncodedStr = base64.b64encode(val)
    _LOGGER.debug(base64EncodedStr)
	
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
            vacbot.refresh_statuses()
            #vacbot.request_all_statuses()
            #action.wait.wait(vacbot)
        vacbot.disconnect(wait=True)
		
        _LOGGER.debug("Battery Status: {}".format(vacbot.battery_status))
        _LOGGER.debug("Vacuum Status: {}".format(vacbot.vacuum_status))
        _LOGGER.debug("Fan Speed: {}".format(vacbot.fan_speed))
		
    click.echo("done")


if __name__ == '__main__':
    cli()
