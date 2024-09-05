from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse, urlunparse

if TYPE_CHECKING:
    from typing import Any

    from .types import Filter, Headers


def _filter_headers(headers: Headers, _filter: Filter) -> Headers:
    headers = dict(headers)

    for i, replacement in _filter.items():
        if i not in headers:
            continue

        if replacement is None:
            del headers[i]
        else:
            headers[i] = replacement

    return headers


def _filter_querystring(
    querystring: dict[str, Any] | str, _filter: Filter
) -> dict[str, Any]:
    if isinstance(querystring, str):
        querystring = dict(parse_qs(querystring))

    for i, replacement in _filter.items():
        if i not in querystring:
            continue

        if replacement is None:
            del querystring[i]
        else:
            querystring[i] = replacement

    return querystring


def _remove_querystring(uri: str) -> str:
    scheme, netloc, path, params, _, fragment = urlparse(uri)

    return urlunparse((scheme, netloc, path, params, "", fragment))


def _filter_uri(uri: str, _filter: Filter) -> str:
    uri = _remove_querystring(uri)

    for i, replacement in _filter.items():
        if i not in uri:
            continue

        if replacement is None:
            uri = uri.replace(i, "")
        else:
            uri = uri.replace(i, replacement)

    if re.search(r"^\w+://[^/]+[.]\w{2,}(:[0-9]+)?$", uri):
        uri += "/"

    return uri
