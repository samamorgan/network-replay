import re
from urllib.parse import parse_qs


def _filter_headers(headers, _filter):
    for i in _filter:
        replacement = None
        if isinstance(i, (list, tuple)):
            i, replacement = i

        if i not in headers:
            continue

        if replacement is None:
            del headers[i]
        else:
            headers[i] = replacement

    return headers


def _filter_querystring(querystring, _filter):
    if isinstance(querystring, str):
        querystring = dict(parse_qs(querystring))

    for i in _filter:
        replacement = None
        if isinstance(i, (list, tuple)):
            i, replacement = i

        if i not in querystring:
            continue

        if replacement is None:
            del querystring[i]
        else:
            querystring[i] = replacement

    return querystring


def _filter_uri(uri: str, _filter) -> str:
    for i in _filter:
        replacement = None
        if isinstance(i, (list, tuple)):
            i, replacement = i

        if i not in uri:
            continue

        if replacement is None:
            uri = uri.replace(i, "")
        else:
            uri = uri.replace(i, replacement)

    if re.search(r"^\w+://[^/]+[.]\w{2,}(:[0-9]+)?$", uri):
        uri += "/"

    return uri
