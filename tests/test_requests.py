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


@pytest.mark.parametrize(
    "method",
    [
        "delete",
        "get",
        "patch",
        "post",
        "put",
    ],
)
def test_request_methods(method):
    session = TestSession()
    response = getattr(session, method)()
    assert response.status_code == 200
    assert (base_path / "recordings" / f"TestSession.{method}.json").exists()
