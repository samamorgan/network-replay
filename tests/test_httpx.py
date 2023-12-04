from http import HTTPStatus

import httpx
import pytest
from PIL import Image


class TestHttpx:
    @pytest.mark.network_replay
    def test_delete(self):
        response = httpx.delete("https://httpbin.org/delete")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_get(self):
        response = httpx.get("https://httpbin.org/get")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_head(self):
        response = httpx.head("https://httpbin.org/status/200")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_options(self):
        response = httpx.options("https://httpbin.org/json")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_patch(self):
        response = httpx.patch("https://httpbin.org/patch")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_post(self):
        response = httpx.post("https://httpbin.org/post")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_put(self):
        response = httpx.put("https://httpbin.org/put")
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_multipart_post(self):
        response = httpx.post(
            "https://httpbin.org/anything", files={"file": ("test.txt", "test")}
        )
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.network_replay
    def test_image_get(self):
        response = httpx.get("https://httpbin.org/image/jpeg")
        assert response.status_code == HTTPStatus.OK

        image = Image.open(response)
        assert image.verify() is None
