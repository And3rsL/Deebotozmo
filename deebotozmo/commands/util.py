"""Commands util module."""
from enum import IntEnum
from typing import Type, TypeVar, Union

T = TypeVar("T", bound=IntEnum)


def get_member(enum: Type[T], value: Union[str, T]) -> int:
    """Return the enum member for the given "value" string.

    :param enum: The enum
    :param value: The value, which should be checked.
    :raise ValueError: if the given value don't correspond to a enum member
    :return: The found enum member
    """
    if isinstance(value, enum):
        return value.value

    value = str(value).upper()
    if value not in enum.__members__:
        raise ValueError(f"'{value}' is not a valid {enum.__name__}")

    return enum[value].value
