import pytest
import requests

from network_replay import replay


@replay
@pytest.mark.recording_check
def test_delete():
    response = requests.delete("https://httpbin.org/delete")
    assert response.status_code == 200


@replay
@pytest.mark.recording_check
def test_get():
    response = requests.get("https://httpbin.org/get")
    assert response.status_code == 200


@replay
@pytest.mark.recording_check
def test_head():
    response = requests.head("https://httpbin.org/json")
    assert response.status_code == 200


@replay
@pytest.mark.recording_check
def test_options():
    response = requests.options("https://httpbin.org/json")
    assert response.status_code == 200


@replay
@pytest.mark.recording_check
def test_patch():
    response = requests.patch("https://httpbin.org/patch")
    assert response.status_code == 200


@replay
@pytest.mark.recording_check
def test_post():
    response = requests.post("https://httpbin.org/post")
    assert response.status_code == 200


@replay
@pytest.mark.recording_check
def test_put():
    response = requests.put("https://httpbin.org/put")
    assert response.status_code == 200


@replay
@pytest.mark.recording_check
def test_multipart_post():
    response = requests.post(
        "https://httpbin.org/anything", files={"file": ("test.txt", "test")}
    )
    assert response.status_code == 200


@replay
@pytest.mark.recording_check
@pytest.mark.skip(reason="https://github.com/gabrielfalcao/HTTPretty/issues/477")
def test_image_get():
    response = requests.get("https://httpbin.org/image/jpeg")
    assert response.status_code == 200
