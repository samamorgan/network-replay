from pathlib import Path

import pytest
import requests

from network_replay import replay

base_path = Path(__file__).parent


class TestSession(requests.Session):
    host = "https://httpbin.org/"

    @replay
    def delete(self):
        return super().delete(f"{self.host}/delete")

    @replay
    def get(self):
        return super().get(f"{self.host}/get")

    @replay
    def patch(self):
        return super().patch(f"{self.host}/patch")

    @replay
    def post(self):
        return super().post(f"{self.host}/post")

    @replay
    def put(self):
        return super().put(f"{self.host}/put")


@replay
def file_post():
    return requests.post(
        "https://httpbin.org/anything", files={"file": ("test.txt", "test")}
    )


@replay
def image_get():
    return requests.get("https://httpbin.org/image/jpeg")


@pytest.mark.parametrize(
    "method_name",
    [
        "delete",
        "get",
        "patch",
        "post",
        "put",
    ],
)
def test_request_methods(method_name):
    session = TestSession()
    response = getattr(session, method_name)()
    assert response.status_code == 200
    assert (base_path / "recordings" / f"TestSession.{method_name}.json").exists()


def test_multipart_post():
    response = file_post()
    assert response.status_code == 200
    assert (base_path / "recordings" / "file_post.json").exists()


@pytest.mark.skip(reason="https://github.com/gabrielfalcao/HTTPretty/issues/477")
def test_image_get():
    response = image_get()
    assert response.status_code == 200
    assert (base_path / "recordings" / "image_get.json").exists()
