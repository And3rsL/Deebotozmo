import hashlib
import os
from typing import Union


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
