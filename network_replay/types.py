from http.client import HTTPMessage
from pathlib import Path
from re import Pattern
from typing import Any, Callable, TypedDict, Union

from httpretty.core import HTTPrettyRequest  # type: ignore[import-untyped]

from .core import RecordMode
from .serializers import Serializer

Body = Union[str, bytes, dict[str, Any], list[Any]]
Replacement = Union[str, Pattern, Callable[[Any], Any], None]
Filter = dict[str, Replacement]
Headers = dict[str, Union[str, None]]
ResponseInfo = tuple[int, HTTPMessage, bytes]
CallableBody = Callable[[HTTPrettyRequest, str, Headers], ResponseInfo]
GenericCallable = Callable[..., Any]


class ReplayConfig(TypedDict):
    path: Path
    record_on_error: bool
    filter_headers: Filter
    filter_querystring: Filter
    filter_uri: Filter
    serializer: type[Serializer]
    record_mode: RecordMode


class RequestDict(TypedDict):
    uri: str
    method: str
    headers: Headers
    body: Body
    querystring: dict[str, str]


class ResponseDict(TypedDict):
    status: int
    body: Body
    headers: Headers


class Transaction(TypedDict):
    request: RequestDict
    response: ResponseDict


Transactions = list[Transaction]
