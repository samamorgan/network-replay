from __future__ import annotations

import json
import logging
import re
from ast import literal_eval
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from httpretty.core import (  # type: ignore
    MULTILINE_ANY_REGEX,
    SOCKET_GLOBAL_DEFAULT_TIMEOUT,
    URIInfo,
    URIMatcher,
    httpretty,
)

from .exceptions import RecordingDisabledError
from .filters import _filter_headers, _filter_querystring, _filter_uri
from .serializers import JSONSerializer

if TYPE_CHECKING:
    from http.client import HTTPMessage
    from re import Pattern
    from typing import Any

    from httpretty.core import Entry, HTTPrettyRequest

    from .serializers import Serializer


logger = logging.getLogger(__name__)


def replay(
    func: Callable[..., Any] | None = None,
    *,
    directory: str = "recordings",
    **manager_kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def inner(func: Callable[..., Any]) -> Callable[..., Any]:
        path = _recording_path(func, directory)

        nonlocal manager_kwargs
        manager_kwargs = {"path": path, **manager_kwargs}

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with ReplayManager(**manager_kwargs) as _:
                return func(*args, **kwargs)

        return wrapper

    if func is not None:
        return inner(func)
    return inner


def _recording_path(func: Callable[..., Any], subdir: str) -> Path:
    qualname_split = func.__qualname__.split(".")
    try:
        split_index = qualname_split.index("<locals>") + 1
    except ValueError:
        split_index = 0
    qualname = ".".join(qualname_split[split_index:])

    return Path(func.__code__.co_filename).parent / subdir / f"{qualname}.json"


class RecordMode(Enum):
    APPEND = "append"
    """Recording on, replay on, re-write the recording."""
    BLOCK = "block"
    """Recording off, replay off, raise an error on any request."""
    ONCE = "once"
    """Recording on, replay on, raise an error on new requests."""
    OVERWRITE = "overwrite"
    """Recording on, replay off, overwrite any existing recording."""
    REPLAY_ONLY = "replay_only"
    """Recording off, replay on, raise an error on new requests."""


class ReplayManager(httpretty):  # type: ignore
    def __init__(
        self,
        path: Path | str,
        record_on_error: bool = False,
        filter_headers: dict[str, str | None] = {},
        filter_querystring: dict[str, str | None] = {},
        filter_uri: dict[str, str | None] = {},
        serializer: type[Serializer] = JSONSerializer,
        record_mode: RecordMode = RecordMode.ONCE,
    ):
        self.record_on_error = record_on_error
        self.filter_headers = filter_headers
        self.filter_querystring = filter_querystring
        self.filter_uri = filter_uri
        self.serializer = serializer(Path(path).resolve())
        self.record_mode = RecordMode(record_mode)

        self._cycle_sequence: list[dict[str, Any]] = []

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} with {len(self._entries)} URI entries>"

    def __enter__(self) -> ReplayManager:
        self.reset()

        if self.recording_exists:
            logger.debug(f"Replaying interactions from {self.path}")
            self.enable(allow_net_connect=False)
            self._register_recorded_requests()

            return self

        logger.debug("Recording network interactions")
        self.enable(allow_net_connect=True)

        for method in self.METHODS:
            self.register_uri(method, MULTILINE_ANY_REGEX, body=self._record_request)

        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.disable()
        self.reset()

        if not self.record_on_error and exc_type is not None:
            logger.debug("Not recording due to error")
            return

        if self.recording_exists:
            logger.debug("No recording in replay mode")
            return

        if not self.can_record:
            logger.debug("Recording is disabled")
            return

        logger.debug(f"Writing interactions to {self.path}")
        self.serializer.serialize(self._cycle_sequence)

    @property
    def can_replay(self) -> bool:
        return self.record_mode in (
            RecordMode.APPEND,
            RecordMode.ONCE,
            RecordMode.REPLAY_ONLY,
        )

    @property
    def can_record(self) -> bool:
        return self.record_mode in (
            RecordMode.APPEND,
            RecordMode.ONCE,
            RecordMode.OVERWRITE,
        )

    @property
    def path(self) -> Path:
        return self.serializer.path

    @property
    def recording_exists(self) -> bool:
        return self.path.exists()

    def register_uri(
        self,
        method: str,
        uri: str,
        body: str = '{"message": "ReplayManager :)"}',
        adding_headers: dict[str, Any] | None = None,
        forcing_headers: dict[str, Any] | None = None,
        status: int = 200,
        responses: list[Entry] | None = None,
        match_querystring: bool = False,
        priority: int = 0,
        **headers: Any,
    ) -> None:
        """Override of `httpretty.core.register_uri` to support alternative filtering."""
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

    def _register_recorded_requests(self) -> None:
        """Register recorded requests for playback.

        Since serializing responses modifies the original response length, we need to
        dynamically calculate the Content-Length header to pass httpretty's validation.
        """
        self._cycle_sequence = self.serializer.deserialize()

        for item in self._cycle_sequence:
            body = str(item["response"]["body"])
            if body.startswith("b'"):
                body = literal_eval(body)

            self.register_uri(
                method=item["request"]["method"],
                uri=self._add_querystring(
                    item["request"]["uri"], item["request"]["querystring"]
                ),
                body=body,
                forcing_headers=item["response"]["headers"],
                status=item["response"]["status"],
                match_querystring=True,
            )

    def _record_request(
        self, request: HTTPrettyRequest, uri: str, headers: dict[str, Any]
    ) -> tuple[int, HTTPMessage, bytes]:
        if not self.can_record:
            raise RecordingDisabledError(
                f"Recording is disabled with {self.record_mode}"
            )

        self.disable()

        _request = Request(
            uri,
            data=request.body or None,
            headers=request.headers,
            method=request.method,
        )
        response = urlopen(
            _request, timeout=request.timeout or SOCKET_GLOBAL_DEFAULT_TIMEOUT
        )
        response_body = response.read()
        decoded_response_body = self._decode_body(response_body)

        request_dict = {
            "uri": _filter_uri(uri, self.filter_uri),
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

        self._cycle_sequence.append(
            {
                "request": request_dict,
                "response": response_dict,
            }
        )

        self.enable(allow_net_connect=True)

        return response.status, response.headers, response_body

    def _add_querystring(self, uri: str, querystring: dict[str, Any]) -> str:
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

    def _calculate_body_length(self, body: str | dict[str, Any]) -> str | None:
        """Calculate the body length for a response.

        Args:
            body (str | dict): The response body.

        Returns:
            str | None: The body length as an integer string, or None if the body is binary.
        """
        if isinstance(body, str) and body.startswith("b'"):
            return None

        return str(len(str(body)))


class ReplayURIMatcher(URIMatcher):  # type: ignore
    regex: Pattern[str] | None
    info: URIInfo | None

    def __init__(
        self,
        uri: str,
        entries: list[Entry],
        match_querystring: bool = False,
        priority: int = 0,
        filter_uri: dict[str, str | None] = {},
        filter_querystring: dict[str, str | None] = {},
    ):
        super().__init__(uri, entries, match_querystring, priority)

        self.filter_uri = filter_uri
        self.filter_querystring = filter_querystring

    def matches(self, info: URIInfo) -> bool:
        if self.info:
            return self.info_matches(info) and self.query_matches(info)

        if self.regex:
            if self.regex.search(
                info.full_url(use_querystring=self._match_querystring)
            ):
                return True

        return False

    def info_matches(self, info: URIInfo) -> bool:
        filtered_uri = _filter_uri(info.full_url(), self.filter_uri)

        if URIInfo.from_uri(filtered_uri, info.last_request) == self.info:
            return True

        return False

    def query_matches(self, info: URIInfo) -> bool:
        if not self._match_querystring:
            return True

        if self.info:
            filtered_query = urlencode(
                _filter_querystring(info.query, self.filter_querystring), doseq=True
            )
            if self.info.query == filtered_query:
                return True

        return False
