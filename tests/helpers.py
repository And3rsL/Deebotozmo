from typing import Set, Type

from deebotozmo.util import DisplayNameIntEnum


def verify_DisplayNameEnum_unique(enum: Type[DisplayNameIntEnum]):
    assert issubclass(enum, DisplayNameIntEnum)
    names: Set[str] = set()
    values: Set[int] = set()
    for member in enum:
        assert member.value not in values
        values.add(member.value)

        name = member.name.lower()
        assert name not in names
        names.add(name)

        display_name = member.display_name.lower()
        if display_name != name:
            assert display_name not in names
            names.add(display_name)