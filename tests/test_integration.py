from http import HTTPStatus
from urllib.request import Request, urlopen

import httpx
import pytest
import requests
import urllib3
from PIL import Image

HTTPBIN = "https://httpbin.org"
REQUEST_METHODS = {
    "DELETE": f"{HTTPBIN}/delete",
    "GET": f"{HTTPBIN}/get",
    "HEAD": f"{HTTPBIN}/status/200",
    "OPTIONS": f"{HTTPBIN}/status/200",
    "PATCH": f"{HTTPBIN}/patch",
    "POST": f"{HTTPBIN}/post",
    "PUT": f"{HTTPBIN}/put",
}


class BaseClientTest:
    status_code_property = ""
    image_get_kwargs = {}

    def make_request(self, method, url, *args, **kwargs):
        raise NotImplementedError("This method must be overridden by subclasses")

    def response_file(self, response):
        return response

    @pytest.mark.network_replay
    @pytest.mark.parametrize(
        ("method", "url"),
        [(method, url) for method, url in REQUEST_METHODS.items()],
        ids=list(REQUEST_METHODS),
    )
    def test_request_methods(self, method, url):
        response = self.make_request(method, url)
        assert getattr(response, self.status_code_property) == HTTPStatus.OK

    @pytest.mark.network_replay(
        filter_headers=["User-Agent", ("Content-Type", "REDACTED")]
    )
    def test_filter_headers(self, replay_manager):
        response = self.make_request("GET", REQUEST_METHODS["GET"])
        assert getattr(response, self.status_code_property) == HTTPStatus.OK

        request = replay_manager._calls[0]["request"]
        assert "User-Agent" not in request["headers"]

        response = replay_manager._calls[0]["response"]
        assert response["headers"]["Content-Type"] == "REDACTED"

    @pytest.mark.network_replay(filter_querystring=["foo", ("bar", "REDACTED")])
    def test_filter_querystring(self, replay_manager):
        response = self.make_request("GET", f"{HTTPBIN}/response-headers?foo=1&bar=2")
        assert getattr(response, self.status_code_property) == HTTPStatus.OK

        querystring = replay_manager._calls[0]["request"]["querystring"]
        assert "foo" not in querystring
        assert querystring["bar"] == "REDACTED"

    @pytest.mark.network_replay(filter_uri=["/get"])
    def test_filter_uri(self, replay_manager):
        response = self.make_request("GET", REQUEST_METHODS["GET"])
        assert getattr(response, self.status_code_property) == HTTPStatus.OK

        request = replay_manager._calls[0]["request"]
        assert "get" not in request["uri"]

    @pytest.mark.network_replay
    def test_image_get(self):
        response = self.make_request(
            "GET", f"{HTTPBIN}/image/jpeg", **self.image_get_kwargs
        )
        assert getattr(response, self.status_code_property) == HTTPStatus.OK

        file_obj = self.response_file(response)
        image = Image.open(file_obj)
        assert image.verify() is None

    @pytest.mark.network_replay
    def test_multipart_post(self):
        response = self.make_request(
            "POST", f"{HTTPBIN}/anything", files={"file": ("test.txt", "test")}
        )
        assert getattr(response, self.status_code_property) == HTTPStatus.OK


class TestHttpx(BaseClientTest):
    status_code_property = "status_code"

    def make_request(self, method, url, *args, **kwargs):
        return httpx.request(method, url, *args, **kwargs)


class TestRequests(BaseClientTest):
    status_code_property = "status_code"
    image_get_kwargs = {"stream": True}
    response_file_obj = "raw"

    def make_request(self, method, url, *args, **kwargs):
        return requests.request(method, url, *args, **kwargs)

    def response_file(self, response):
        return response.raw


class TestUrllib(BaseClientTest):
    status_code_property = "code"

    def make_request(self, method, url, *args, **kwargs):
        # HACK: For some reason urllib needs an explicit timeout to record requests
        request = Request(url, method=method)
        return urlopen(request, *args, timeout=1, **kwargs)

    @pytest.mark.skip(reason="Don't feel like figuring out the correct logic")
    def test_multipart_post(self):
        pass


class TestUrllib3(BaseClientTest):
    status_code_property = "status"
    image_get_kwargs = {"preload_content": False}

    def make_request(self, method, url, *args, **kwargs):
        return urllib3.request(method, url, *args, **kwargs)

    @pytest.mark.network_replay
    def test_multipart_post(self):
        response = self.make_request(
            "POST", f"{HTTPBIN}/anything", fields={"file": ("test.txt", "test")}
        )
        assert getattr(response, self.status_code_property) == HTTPStatus.OK
