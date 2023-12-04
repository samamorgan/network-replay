from http import HTTPStatus

import pytest
import requests
from PIL import Image


class TestRequests:
    @pytest.mark.network_replay
    def test_delete(self):
        response = requests.delete("https://httpbin.org/delete")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_get(self):
        response = requests.get("https://httpbin.org/get")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_head(self):
        response = requests.head("https://httpbin.org/status/200")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_options(self):
        response = requests.options("https://httpbin.org/json")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_patch(self):
        response = requests.patch("https://httpbin.org/patch")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_post(self):
        response = requests.post("https://httpbin.org/post")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_put(self):
        response = requests.put("https://httpbin.org/put")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_multipart_post(self):
        response = requests.post(
            "https://httpbin.org/anything", files={"file": ("test.txt", "test")}
        )
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_image_get(self):
        response = requests.get("https://httpbin.org/image/jpeg", stream=True)
        assert response.status_code == HTTPStatus.OK

        image = Image.open(response.raw)
        assert image.verify() is None
