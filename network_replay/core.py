import json
import logging
import re
from ast import literal_eval
from functools import wraps
from pathlib import Path
from socket import _GLOBAL_DEFAULT_TIMEOUT
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from httpretty.core import MULTILINE_ANY_REGEX, URIInfo, URIMatcher, httpretty

from .filters import _filter_headers, _filter_querystring, _filter_uri
from .serializers import JSONSerializer

logger = logging.getLogger(__name__)


def replay(func: Callable = None, *, directory="recordings") -> Callable:
    def inner(func: Callable):
        path = _recording_path(func, directory)

        @wraps(func)
        def wrapper(*args, **kwargs):
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
    def __init__(
        self,
        path: Path | str,
        record_on_error: bool = False,
        filter_headers: list | tuple = (),
        filter_querystring: list | tuple = (),
        filter_uri: list | tuple = (),
        serializer: Callable = JSONSerializer,
    ):
        self.record_on_error = record_on_error
        self.filter_headers = filter_headers
        self.filter_querystring = filter_querystring
        self.filter_uri = filter_uri
        self.serializer = serializer(Path(path).resolve())

        self._calls = []

    def __str__(self):
        return f"<{self.__class__.__name__} with {len(self._entries)} URI entries>"

    def __enter__(self):
        self.reset()

        if self._replay_mode:
            logger.debug(f"Replaying interactions from {self.serializer.path}")
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

        if self._replay_mode:
            logger.debug("No recording in replay mode")
            return

        logger.debug(f"Writing interactions to {self.serializer.path}")
        self.serializer.serialize(self._calls)

    @property
    def _replay_mode(self):
        return self.serializer.path.exists()

    def register_uri(
        self,
        method,
        uri,
        body='{"message": "ReplayManager :)"}',
        adding_headers=None,
        forcing_headers=None,
        status=200,
        responses=None,
        match_querystring=False,
        priority=0,
        **headers,
    ):
        """Override of `httpretty.core.register_uri` to support filtering."""
        uri_is_string = isinstance(uri, str)

        if uri_is_string and re.search(r"^\w+://[^/]+[.]\w{2,}(:[0-9]+)?$", uri):
            uri += "/"

        if isinstance(responses, list) and len(responses) > 0:
            for response in responses:
                response.uri = uri
                response.method = method
            entries_for_this_uri = responses
        else:
            headers["body"] = body
            headers["adding_headers"] = adding_headers
            headers["forcing_headers"] = forcing_headers
            headers["status"] = status

            entries_for_this_uri = [
                self.Response(method=method, uri=uri, **headers),
            ]

        matcher = ReplayURIMatcher(
            uri,
            entries_for_this_uri,
            match_querystring,
            priority,
            self.filter_uri,
            self.filter_querystring,
        )
        if matcher in self._entries:
            matcher.entries.extend(self._entries[matcher])
            del self._entries[matcher]

        self._entries[matcher] = entries_for_this_uri

    def _register_recorded_requests(self):
        """Register recorded requests for playback.

        Since serializing responses modifies the original response length, we need to
        dynamically calculate the Content-Length header to pass httpretty's validation.
        """
        self._calls = self.serializer.deserialize()

        for item in self._calls:
            body = str(item["response"]["body"])
            if body.startswith("b'"):
                body = literal_eval(body)

            response_headers = item["response"]["headers"]
            # if "Content-Length" in response_headers:
            #     response_headers["Content-Length"] = str(len(body))

            self.register_uri(
                method=item["request"]["method"],
                # uri=self._generate_uri_regex(
                #     item["request"]["uri"], item["request"]["querystring"]
                # ),
                uri=self._add_querystring(
                    item["request"]["uri"], item["request"]["querystring"]
                ),
                body=body,
                forcing_headers=response_headers,
                status=item["response"]["status"],
                match_querystring=True,
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
        decoded_response_body = self._decode_body(response_body)

        request_dict = {
            "uri": _filter_uri(self._remove_querystring(uri), self.filter_uri),
            "method": request.method,
            "headers": _filter_headers(dict(request.headers), self.filter_headers),
            "body": self._decode_body(request.body),
            "querystring": _filter_querystring(
                request.querystring, self.filter_querystring
            ),
        }
        response_dict = {
            "status": response.status,
            "body": decoded_response_body,
            "headers": _filter_headers(dict(response.headers), self.filter_headers),
        }

        # Since serializing responses modifies the original response length, we need to
        # calculate the Content-Length header to pass httpretty's validation.
        if "Content-Length" in response_dict["headers"]:
            body_length = self._calculate_body_length(decoded_response_body)
            if body_length is not None:
                response_dict["headers"]["Content-Length"] = body_length

        self._calls.append(
            {
                "request": request_dict,
                "response": response_dict,
            }
        )

        self.enable(allow_net_connect=True)

        return response.status, response.headers, response_body

    def _remove_querystring(self, uri):
        scheme, netloc, path, params, _, fragment = urlparse(uri)

        return urlunparse((scheme, netloc, path, params, "", fragment))

    def _add_querystring(self, uri, querystring):
        scheme, netloc, path, params, query, fragment = urlparse(uri)
        combined_query = urlencode({**parse_qs(query), **querystring}, doseq=True)

        return urlunparse((scheme, netloc, path, params, combined_query, fragment))

    def _decode_body(self, body: bytes) -> str | Any:
        try:
            decoded_body = body.decode()
        except UnicodeDecodeError:
            decoded_body = str(body)

        try:
            return json.loads(decoded_body)
        except json.JSONDecodeError:
            pass

        return decoded_body

    def _calculate_body_length(self, body: str | dict) -> str | None:
        """Calculate the body length for a response.

        Args:
            body (str | dict): The response body.

        Returns:
            str | None: The body length as an integer string, or None if the body is binary.
        """
        if isinstance(body, str) and body.startswith("b'"):
            return None

        return str(len(str(body)))


class ReplayURIMatcher(URIMatcher):
    regex = None
    info = None

    def __init__(
        self,
        uri,
        entries,
        match_querystring=False,
        priority=0,
        filter_uri=(),
        filter_querystring=(),
    ):
        super().__init__(uri, entries, match_querystring, priority)

        self.filter_uri = filter_uri
        self.filter_querystring = filter_querystring

    def matches(self, info):
        if self.info:
            # Query string is not considered when comparing info objects, compare separately
            return self.info_matches(info) and (
                not self._match_querystring or self.query_matches(info)
            )
        else:
            return self.regex.search(
                info.full_url(use_querystring=self._match_querystring)
            )

    def info_matches(self, info):
        filtered_uri = _filter_uri(info.full_url(), self.filter_uri)

        return URIInfo.from_uri(filtered_uri, info.last_request) == self.info

    def query_matches(self, info):
        filtered_query = urlencode(
            _filter_querystring(info.query, self.filter_querystring), doseq=True
        )

        return self.info.query == filtered_query
