"""Tasmota config validation."""
from typing import Any, List, TypeVar, Union

import voluptuous as vol

# typing typevar
T = TypeVar("T")  # pylint: disable=invalid-name

bit = vol.All(vol.Coerce(int), vol.Range(min=0, max=1))


positive_int = vol.All(  # pylint: disable=invalid-name
    vol.Coerce(int), vol.Range(min=0)
)


def ensure_list(value: Union[T, List[T], None]) -> List[T]:
    """Wrap value in list if it is not one."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def optional_string(value: Any) -> str:
    """Coerce value to string, except for None."""
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        raise vol.Invalid("value should be a string")

    return str(value)


def string(value: Any) -> str:
    """Coerce value to string, except for None."""
    if value is None:
        raise vol.Invalid("string value is None")
    if isinstance(value, (list, dict)):
        raise vol.Invalid("value should be a string")

    return str(value)
