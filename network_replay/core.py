import json
import logging
from ast import literal_eval
from functools import wraps
from pathlib import Path
from socket import _GLOBAL_DEFAULT_TIMEOUT
from typing import Callable
from urllib.request import Request, urlopen

from httpretty.core import MULTILINE_ANY_REGEX, httpretty

logger = logging.getLogger(__name__)


def replay(func: Callable = None, *, directory="recordings") -> Callable:
    def inner(func: Callable):
        path = _recording_path(func, directory)

        @wraps(func)
        def wrapper(*args, **kwargs):
            path.parent.mkdir(exist_ok=True)

            with ReplayManager(path):
                return func(*args, **kwargs)

        return wrapper

    if func:
        return inner(func)
    return inner


def _recording_path(func, subdir) -> Path:
    qualname_split = func.__qualname__.split(".")
    try:
        split_index = qualname_split.index("<locals>") + 1
    except ValueError:
        split_index = 0
    qualname = ".".join(qualname_split[split_index:])

    return Path(func.__code__.co_filename).parent / subdir / f"{qualname}.json"


class ReplayManager(httpretty):
    def __init__(self, path: Path, record_on_error=False):
        self.path = path
        self.record_on_error = record_on_error

        self._calls = []

    def __enter__(self):
        self.reset()

        if self.path.exists():
            logger.debug(f"Replaying interactions from {self.path}")
            self.enable(allow_net_connect=False)
            self._register_recorded_requests()

            return self

        logger.debug("Recording network interactions")
        self.enable(allow_net_connect=True)

        for method in self.METHODS:
            self.register_uri(method, MULTILINE_ANY_REGEX, body=self._record_request)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disable()
        self.reset()

        if not self.record_on_error and exc_type is not None:
            logger.debug("Not recording due to error")
            return

        if not self._calls:
            logger.debug("No interactions to record")
            return

        logger.debug(f"Writing interactions to {self.path}")
        self.path.parent.mkdir(exist_ok=True)

        with self.path.open("w") as f:
            # TODO: Pluggable serializer, ex. for YAML support.
            json.dump(self._calls, f, indent=2)

    def _register_recorded_requests(self):
        for item in json.load(self.path.open()):
            body = item["response"]["body"]
            if body.startswith("b'"):
                body = literal_eval(body)

            self.register_uri(
                method=item["request"]["method"],
                uri=item["request"]["uri"],
                body=body,
                forcing_headers=item["response"]["headers"],
                status=item["response"]["status"],
            )

    def _record_request(self, request, uri, headers):
        self.disable()

        _request = Request(
            uri,
            data=request.body or None,
            headers=request.headers,
            method=request.method,
        )
        response = urlopen(_request, timeout=request.timeout or _GLOBAL_DEFAULT_TIMEOUT)
        response_body = response.read()

        self._calls.append(
            {
                "request": {
                    "uri": uri,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "body": self._decode_body(request.body),
                    "querystring": request.querystring,
                },
                "response": {
                    "status": response.status,
                    "body": self._decode_body(response_body),
                    "headers": dict(response.headers),
                },
            }
        )

        self.enable(allow_net_connect=True)

        return response.status, response.headers, response_body

    def _decode_body(self, body: bytes) -> str:
        try:
            return body.decode()
        except UnicodeDecodeError:
            return str(body)
