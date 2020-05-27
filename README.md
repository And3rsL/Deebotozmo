<a href="https://www.buymeacoffee.com/4nd3rs" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-black.png" width="150px" height="35px" alt="Buy Me A Coffee" style="height: 35px !important;width: 150px !important;" ></a>

=====
# Library for DeebotOzmo 960/950/920

A simple command-line python script to drive a robot vacuum. Currently
known to work with the Ecovacs Deebot 960/950/920 from both North America and Europe.

## Installation

If you have a recent version of Python 3, you should be able to
do `pip install deebotozmo` to get the most recently released version of
this.

## Usage

To get started, you'll need to have already set up an EcoVacs account
using your smartphone.

With that ready, step one is to log in:
```
    % deebotozmo createconfig
    Ecovacs app email: [your email]
    Ecovacs app password: [your password]
    your two-letter country code: us
    your two-letter continent code: na
    Config saved.
```

That creates a config file in a platform-appropriate place. The password
is hashed before saving, so it's reasonably safe. (If it doesn't appear
to work for your continent, try "ww", their world-wide catchall.)

With that set up, you could have it clean in auto mode for 10 minutes
and return to its charger:

```
    % deebotozmo clean
```

To tell it to go plug in:

```
    % deebotozmo charge
```

## Library use

You are welcome to try using this as a python library for other efforts.
A simple usage might go something like this:

```
import deebotozmo

config = ...

api = EcoVacsAPI(config['device_id'], config['email'], config['password_hash'],
                         config['country'], config['continent'])
my_vac = api.devices()[0]
vacbot = VacBot(api.uid, api.REALM, api.resource, api.user_access_token, my_vac, config['continent'])
vacbot.connect_and_wait_until_ready()

vacbot.Clean()  # start cleaning
time.sleep(900)      # clean for 15 minutes
vacbot.Charge() # return to the charger
```

## Thanks

My heartfelt thanks to:

* [sucks](https://github.com/wpietri/sucks),
After all, this is a sucks fork :)
* [xmpppeek](https://www.beneaththewaves.net/Software/XMPPPeek.html),
a great library for examining XMPP traffic flows (yes, your vacuum
speaks Jabbber!),
* [mitmproxy](https://mitmproxy.org/), a fantastic tool for analyzing HTTPS,
* [click](http://click.pocoo.org/), a wonderfully complete and thoughtful
library for making Python command-line interfaces,
* [requests](http://docs.python-requests.org/en/master/), a polished Python
library for HTTP requests,
* [Decompilers online](http://www.javadecompilers.com/apk), which was
very helpful in figuring out what the Android app was up to,
* Albert Louw, who was kind enough to post code from [his own
experiments](https://community.smartthings.com/t/ecovacs-deebot-n79/93410/33)
with his device, and
* All the users who have given useful feedback and contributed code!