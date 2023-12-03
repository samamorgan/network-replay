import json
import logging
from functools import wraps
from pathlib import Path
from typing import Callable

from httpretty.core import MULTILINE_ANY_REGEX, httpretty
from urllib3 import PoolManager

logger = logging.getLogger(__name__)


def replay(func: Callable = None, *, directory="recordings") -> Callable:
    def inner(func: Callable):
        path = _recording_path(func, directory)

        @wraps(func)
        def wrapper(*args, **kwargs):
            path.parent.mkdir(exist_ok=True)

            with Recorder(path):
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


class Recorder(httpretty):
    def __init__(self, path: Path, record_on_error=False):
        self.path = path
        self.record_on_error = record_on_error

        self.calls = []
        self.http = None

    def __enter__(self):
        self.reset()

        # Replay previously-recorded interactions
        if self.path.exists():
            self.enable(allow_net_connect=False)
            self._register_recorded_requests()

            return self

        # Record interactions
        self.http = PoolManager()
        self.enable(allow_net_connect=True)

        for method in self.METHODS:
            self.register_uri(method, MULTILINE_ANY_REGEX, body=self._record_request)

    def __exit__(self, exc_type, exc_value, traceback):
        self.disable()
        self.reset()

        if not self.record_on_error and exc_type is not None:
            logging.debug("Not recording due to error")
            return

        if not self.calls:
            logging.debug("No interactions to record")
            return

        logging.debug("Recording interactions")
        self.path.parent.mkdir(exist_ok=True)

        with self.path.open("w") as f:
            json.dump(self.calls, f, indent=2)

    def _register_recorded_requests(self):
        for item in json.load(self.path.open()):
            self.register_uri(
                method=item["request"]["method"],
                uri=item["request"]["uri"],
                body=item["response"]["body"],
                forcing_headers=item["response"]["headers"],
                status=item["response"]["status"],
            )

    def _record_request(self, request, uri, headers):
        self.disable()

        kwargs = {}
        kwargs.setdefault("body", request.body)
        kwargs.setdefault("headers", dict(request.headers))
        response = self.http.request(request.method, uri, **kwargs)

        payload = {}
        payload["request"] = {
            "uri": uri,
            "method": request.method,
            "headers": dict(request.headers),
            "body": self._decode_body(request.body),
            "querystring": request.querystring,
        }
        payload["response"] = {
            "status": response.status,
            "body": self._decode_body(response.data),
            "headers": dict(response.headers),
        }
        self.calls.append(payload)

        self.enable(allow_net_connect=True)

        return response.status, response.headers, response.data

    def _decode_body(self, body):
        try:
            return body.decode()
        except UnicodeDecodeError:
            return body
