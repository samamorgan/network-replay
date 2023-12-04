from http import HTTPStatus

import pytest
import urllib3
from PIL import Image


class TestUrllib3:
    @pytest.mark.network_replay
    def test_delete(self):
        response = urllib3.request("DELETE", "https://httpbin.org/delete")
        assert response.status == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_get(self):
        response = urllib3.request("GET", "https://httpbin.org/get")
        assert response.status == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_head(self):
        response = urllib3.request("HEAD", "https://httpbin.org/status/200")
        assert response.status == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_options(self):
        response = urllib3.request("OPTIONS", "https://httpbin.org/json")
        assert response.status == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_patch(self):
        response = urllib3.request("PATCH", "https://httpbin.org/patch")
        assert response.status == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_post(self):
        response = urllib3.request("POST", "https://httpbin.org/post")
        assert response.status == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_put(self):
        response = urllib3.request("PUT", "https://httpbin.org/put")
        assert response.status == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_multipart_post(self):
        response = urllib3.request(
            "POST",
            "https://httpbin.org/anything",
            fields={"file": ("test.txt", "test")},
        )
        assert response.status == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_image_get(self):
        response = urllib3.request(
            "GET", "https://httpbin.org/image/jpeg", preload_content=False
        )
        assert response.status == HTTPStatus.OK

        image = Image.open(response)
        assert image.verify() is None
