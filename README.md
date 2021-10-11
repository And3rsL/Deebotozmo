![PyPI - Downloads](https://img.shields.io/pypi/dw/deebotozmo)
<a href="https://www.buymeacoffee.com/edenhaus" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-black.png" width="150px" height="35px" alt="Buy Me A Coffee" style="height: 35px !important;width: 150px !important;" ></a>

=====

# Library for DeebotOzmo 960/950/920

A simple command-line python script to drive a robot vacuum. Currently
known to work with the Ecovacs Deebot 960/950/920 from both North America and Europe.

## Installation

If you have a recent version of Python 3, you should be able to
do `pip install deebotozmo` to get the most recently released version of
this.
If you want to use the cli, you need to install it with `pip install deebotozmo[cli]`

## Usage

To get started, you'll need to have already set up an EcoVacs account
using your smartphone.

You are welcome to try using this as a python library for other efforts.
A simple usage might go something like this:

```python
import aiohttp
import asyncio
import logging
import time

from deebotozmo import create_instances
from deebotozmo.commands import *
from deebotozmo.commands.clean import CleanAction
from deebotozmo.models import Configuration
from deebotozmo.mqtt_client import MqttClient
from deebotozmo.events import BatteryEvent
from deebotozmo.util import md5
from deebotozmo.vacuum_bot import VacuumBot

device_id = md5(str(time.time()))
account_id = "your email or phonenumber (cn)"
password_hash = md5("yourPassword")
continent = "eu"
country = "de"


async def main():
  async with aiohttp.ClientSession() as session:
    logging.basicConfig(level=logging.DEBUG)
    config = Configuration(
            device_id, country, continent,session, False
        )

    (authenticator, api_client) = create_instances(config, account_id, password_hash)


    devices_ = await api_client.get_devices()

    bot = VacuumBot(session, devices_[0], api_client)

    mqtt = MqttClient(config, authenticator)
    await mqtt.initialize()
    await mqtt.subscribe(bot)

    async def on_battery(event: BatteryEvent):
      # Do stuff on battery event
      if event.value == 100:
        # Battery full
        pass

    # Subscribe for events (more events available)
    bot.events.battery.subscribe(on_battery)

    # Execute commands
    await bot.execute_command(Clean(CleanAction.START))
    await asyncio.sleep(900)  # Wait for...
    await bot.execute_command(Charge())


if __name__ == '__main__':
  loop = asyncio.get_event_loop()
  loop.create_task(main())
  loop.run_forever()
```

A more advanced example can be found [here](https://github.com/And3rsL/Deebot-for-Home-Assistant).

## Thanks

My heartfelt thanks to:

- [sucks](https://github.com/wpietri/sucks), After all, this is a sucks fork :)
- [xmpppeek](https://www.beneaththewaves.net/Software/XMPPPeek.html), a great library for examining XMPP traffic flows (
  yes, your vacuum speaks Jabbber!),
- [mitmproxy](https://mitmproxy.org/), a fantastic tool for analyzing HTTPS,
- [click](http://click.pocoo.org/), a wonderfully complete and thoughtful library for making Python command-line
  interfaces,
- [requests](http://docs.python-requests.org/en/master/), a polished Python library for HTTP requests,
- [Decompilers online](http://www.javadecompilers.com/apk), which was very helpful in figuring out what the Android app
  was up to,
- Albert Louw, who was kind enough to post code
  from [his own experiments](https://community.smartthings.com/t/ecovacs-deebot-n79/93410/33)
  with his device, and
- All the users who have given useful feedback and contributed code!
