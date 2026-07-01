import os
from typing import Literal, overload


@overload
def read_int_env(name: str, *, required: Literal[True], default: int | None = None) -> int: ...


@overload
def read_int_env(name: str, *, required: Literal[False], default: int) -> int: ...


@overload
def read_int_env(name: str, *, required: Literal[False], default: None = None) -> int | None: ...


def read_int_env(name: str, *, required: bool, default: int | None = None) -> int | None:
    raw = os.getenv(name)
    if not raw:
        if required:
            raise ValueError(f"{name} env var is required")
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} must be a valid integer, got: {raw!r}") from None


def env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
