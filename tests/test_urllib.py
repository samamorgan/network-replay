from http import HTTPStatus
from urllib.request import Request, urlopen

import pytest
from PIL import Image


def make_request(method, url):
    request = Request(url, method=method)
    return urlopen(request, timeout=1)


class TestUrllib:
    @pytest.mark.network_replay
    def test_delete(self):
        response = make_request("DELETE", "https://httpbin.org/delete")
        assert response.code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_get(self):
        response = make_request("GET", "https://httpbin.org/get")
        assert response.code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_head(self):
        response = make_request("HEAD", "https://httpbin.org/status/200")
        assert response.code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_options(self):
        response = make_request("OPTIONS", "https://httpbin.org/status/200")
        assert response.code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_patch(self):
        response = make_request("PATCH", "https://httpbin.org/patch")
        assert response.code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_post(self):
        response = make_request("POST", "https://httpbin.org/post")
        assert response.code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_put(self):
        response = make_request("PUT", "https://httpbin.org/put")
        assert response.code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_image_get(self):
        response = make_request("GET", "https://httpbin.org/image/jpeg")
        assert response.code == HTTPStatus.OK

        image = Image.open(response)
        assert image.verify() is None
