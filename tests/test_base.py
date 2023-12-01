from pathlib import Path

import pytest
import requests

from network_replay import replay

base_path = Path(__file__).parent


@pytest.mark.parametrize(
    "directory",
    ["recordings", "cassettes"],
)
@pytest.mark.skip_recording_check
def test_method_replay_path(directory):
    @replay(directory=directory)
    def get_200():
        return requests.get("https://httpbin.org/status/200")

    response = get_200()
    assert response.status_code == 200
    assert (base_path / directory / "get_200.json").exists()


@pytest.mark.skip_recording_check
def test_class_method_replay_path():
    class Requester:
        @replay
        def get_200(self):
            return requests.get("https://httpbin.org/status/200")

    requester = Requester()
    response = requester.get_200()
    assert response.status_code == 200
    assert (base_path / "recordings" / "Requester.get_200.json").exists()
