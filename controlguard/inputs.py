from collections.abc import Iterable
from decimal import Decimal, DecimalException
import json
import math
from typing import cast

Fields = dict[str, object]


def fields(value: object, name: str = "input") -> Fields:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object.")
    return cast(Fields, value)


def items(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list.")
    return cast(list[object], value)


def string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text.")
    return value


def boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false.")
    return value


def integer(value: object, name: str, allowed: Iterable[int]) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in allowed:
        raise ValueError(f"{name} is missing or outside its allowed integer values.")
    return value


def number(
    value: object, name: str, minimum: Decimal | int = 0, maximum: Decimal | int | None = None
) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name} must be a number.")
    result = Decimal(str(value))
    if not result.is_finite() or result < minimum or (maximum is not None and result > maximum):
        raise ValueError(f"{name} is not finite or falls outside its allowed range.")
    return result


def finite(value: Decimal) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("The calculation exceeds the finite JSON number range.")
    return result


def invalid_constant(value: str) -> object:
    raise ValueError(f"{value} is not a JSON number.")


def unique_object(pairs: list[tuple[str, object]]) -> Fields:
    result: Fields = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate field: {key}.")
        result[key] = value
    return result


def decode(raw: str) -> Fields:
    try:
        return fields(json.loads(
            raw, parse_float=Decimal, parse_constant=invalid_constant, object_pairs_hook=unique_object
        ))
    except DecimalException as error:
        raise ValueError("A JSON number exceeds the supported range.") from error


def encode(payload: object, *, pretty: bool = False) -> str:
    return json.dumps(payload, allow_nan=False, ensure_ascii=True, sort_keys=True,
                      indent=2 if pretty else None, separators=None if pretty else (",", ":"))
