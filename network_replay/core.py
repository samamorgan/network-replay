from collections.abc import Callable
from functools import wraps
from pathlib import Path

from httpretty import HTTPretty


def replay(func: Callable = None, *, directory="recordings"):
    def inner(func: Callable):
        path = _get_recording_path(func, directory)

        @wraps(func)
        def wrapper(*args, **kwargs):
            path.parent.mkdir(exist_ok=True)

            with _get_recording_context(path):
                return func(*args, **kwargs)

        return wrapper

    if func:
        return inner(func)
    return inner


def _get_recording_path(func, subdir):
    qualname_split = func.__qualname__.split(".")
    try:
        split_index = qualname_split.index("<locals>") + 1
    except ValueError:
        split_index = 0
    qualname = ".".join(qualname_split[split_index:])

    return Path(func.__code__.co_filename).parent / subdir / f"{qualname}.json"


def _get_recording_context(path):
    if path.exists():
        return HTTPretty.playback(path, allow_net_connect=False, verbose=True)
    else:
        return HTTPretty.record(path, allow_net_connect=True, verbose=True)
