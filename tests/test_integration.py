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
    @pytest.fixture
    def status_code_property(self) -> str:
        return "status_code"

    @pytest.fixture
    def image_get_kwargs(self) -> dict:
        return {}

    @pytest.fixture
    def request_func(self):
        raise NotImplementedError("This method must be overridden by subclasses")

    @pytest.fixture
    def get_response_file(self):
        return lambda response: response

    @pytest.mark.network_replay
    @pytest.mark.parametrize(
        ("method", "url"),
        [(method, url) for method, url in REQUEST_METHODS.items()],
        ids=list(REQUEST_METHODS),
    )
    def test_request_methods(self, request_func, method, url, status_code_property):
        response = request_func(method, url)
        assert getattr(response, status_code_property) == HTTPStatus.OK

    @pytest.mark.network_replay(
        filter_headers={"User-Agent": None, "Content-Type": "REDACTED"}
    )
    def test_filter_headers(self, request_func, replay_manager, status_code_property):
        response = request_func("GET", REQUEST_METHODS["GET"])
        assert getattr(response, status_code_property) == HTTPStatus.OK

        request = replay_manager._cycle_sequence[0]["request"]
        assert "User-Agent" not in request["headers"]

        response = replay_manager._cycle_sequence[0]["response"]
        assert response["headers"]["Content-Type"] == "REDACTED"

    @pytest.mark.network_replay(filter_querystring={"foo": None, "bar": "REDACTED"})
    def test_filter_querystring(
        self, request_func, replay_manager, status_code_property
    ):
        response = request_func("GET", f"{HTTPBIN}/response-headers?foo=1&bar=2")
        assert getattr(response, status_code_property) == HTTPStatus.OK

        querystring = replay_manager._cycle_sequence[0]["request"]["querystring"]
        assert "foo" not in querystring
        assert querystring["bar"] == "REDACTED"

    @pytest.mark.network_replay(filter_uri={"/get": None})
    def test_filter_uri(self, request_func, status_code_property, replay_manager):
        response = request_func("GET", REQUEST_METHODS["GET"])
        assert getattr(response, status_code_property) == HTTPStatus.OK

        request = replay_manager._cycle_sequence[0]["request"]
        assert "get" not in request["uri"]

    @pytest.mark.network_replay
    def test_image_get(
        self, request_func, image_get_kwargs, status_code_property, get_response_file
    ):
        response = request_func("GET", f"{HTTPBIN}/image/jpeg", **image_get_kwargs)
        assert getattr(response, status_code_property) == HTTPStatus.OK

        file_obj = get_response_file(response)
        image = Image.open(file_obj)
        assert image.verify() is None

    @pytest.mark.network_replay
    def test_multipart_post(self, request_func, status_code_property):
        response = request_func(
            "POST", f"{HTTPBIN}/anything", files={"file": ("test.txt", "test")}
        )
        assert getattr(response, status_code_property) == HTTPStatus.OK


class TestHttpx(BaseClientTest):
    @pytest.fixture
    def request_func(self):
        return httpx.request


class TestRequests(BaseClientTest):
    @pytest.fixture
    def image_get_kwargs(self) -> dict:
        return {"stream": True}

    @pytest.fixture
    def request_func(self):
        return requests.request

    @pytest.fixture
    def get_response_file(self):
        return lambda response: response.raw


class TestUrllib(BaseClientTest):
    @pytest.fixture
    def status_code_property(self) -> str:
        return "code"

    @pytest.fixture
    def request_func(self):
        def request(method, url, *args, **kwargs):
            # HACK: For some reason urllib needs an explicit timeout to record requests
            request = Request(url, method=method)
            return urlopen(request, *args, timeout=1, **kwargs)

        return request

    @pytest.mark.skip(reason="Don't feel like figuring out the correct logic")
    def test_multipart_post(self, request_func):
        pass


class TestUrllib3(BaseClientTest):
    @pytest.fixture
    def image_get_kwargs(self) -> dict:
        return {"preload_content": False}

    @pytest.fixture
    def status_code_property(self) -> str:
        return "status"

    @pytest.fixture
    def request_func(self):
        return urllib3.request

    @pytest.mark.network_replay
    def test_multipart_post(self, request_func, status_code_property):
        response = request_func(
            "POST", f"{HTTPBIN}/anything", fields={"file": ("test.txt", "test")}
        )
        assert getattr(response, status_code_property) == HTTPStatus.OK
