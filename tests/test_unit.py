import json
from http import HTTPStatus
from pathlib import Path
from socket import _GLOBAL_DEFAULT_TIMEOUT
from tempfile import gettempdir

import pytest
import requests

from network_replay import ReplayManager, replay
from network_replay.core import _recording_path
from network_replay.filters import _filter_headers, _filter_querystring, _filter_uri

base_path = Path(__file__).parent


def _get_200():
    return requests.get("https://httpbin.org/status/200")


@pytest.fixture
def mock_request():
    class MockRequest:
        pass

    request = MockRequest()
    request.uri = "https://httpbin.org/foo"
    request.headers = {"User-Agent": "test", "Accept": "application/json"}
    request.body = b""
    request.method = "GET"
    request.querystring = {"foo": 1, "bar": 2}
    request.timeout = _GLOBAL_DEFAULT_TIMEOUT

    return request


class TestReplayDecorator:
    @pytest.mark.parametrize(
        "directory",
        ["recordings", "archive"],
    )
    def test_method_replay_path(self, directory):
        @replay(directory=directory)
        def get_200():
            return _get_200()

        response = get_200()
        assert response.status_code == HTTPStatus.OK
        assert (base_path / directory / "get_200.json").exists()

    def test_class_method_replay_path(self):
        class Requester:
            @replay
            def get_200(self):
                return _get_200()

        response = Requester().get_200()
        assert response.status_code == HTTPStatus.OK
        assert (base_path / "recordings" / "Requester.get_200.json").exists()

    def test__recording_path(self):
        path = _recording_path(_get_200, "recordings")
        assert "<locals>" not in _get_200.__qualname__
        assert path == base_path / "recordings" / "_get_200.json"

        def get_200():
            pass

        path = _recording_path(get_200, "recordings")
        assert "<locals>" in get_200.__qualname__
        assert path == base_path / "recordings" / "get_200.json"


class TestReplayManager:
    @pytest.fixture
    def path(self):
        path = Path(gettempdir(), "test.json")
        yield path
        path.unlink(missing_ok=True)

    @pytest.fixture
    def request_json(self):
        return [
            {
                "request": {
                    "uri": "https://example.org",
                    "method": "GET",
                    "headers": {},
                    "body": "",
                    "querystring": {},
                },
                "response": {
                    "status": 200,
                    "body": "",
                    "headers": {},
                },
            }
        ]

    @pytest.fixture
    def recording(self, path: Path, request_json):
        path.write_text(json.dumps(request_json))
        yield path

    @pytest.fixture
    def manager(self, path):
        return ReplayManager(path=str(path))

    def test___init__(self, path, manager):
        assert manager.serializer.path == path.resolve()
        assert manager.record_on_error is False
        assert manager.filter_headers == ()
        assert manager.filter_querystring == ()
        assert manager.filter_uri == ()
        assert manager._calls == []
        assert manager._replay_mode is False

    def test___str__(self, manager):
        assert str(manager) == "<ReplayManager with 0 URI entries>"

    @pytest.mark.usefixtures("recording")
    def test___enter__replay(self, manager):
        with manager as m:
            assert m.allow_net_connect is False
            assert m._is_enabled is True

    def test___enter__record(self, manager):
        with manager as m:
            assert m.allow_net_connect is True
            assert m._is_enabled is True

    def test___exit___replay(self, manager):
        with manager as m:
            pass

        assert m._is_enabled is False

    def test___exit___record(self, manager):
        with manager as m:
            m._calls.append("test")

        assert m._is_enabled is False
        assert manager.serializer.path.exists()

    def test___exit___record_on_error(self, manager):
        with pytest.raises(Exception):
            with manager as m:
                m.calls.append("test")
                raise Exception

        assert m._is_enabled is False
        assert not manager.serializer.path.exists()

    @pytest.mark.usefixtures("recording")
    def test__register_recorded_requests(self, manager: ReplayManager, request_json):
        manager._register_recorded_requests()
        assert len(manager._entries) == len(request_json)

    def test__record_request(self, manager: ReplayManager, mock_request):
        status, *_ = manager._record_request(
            mock_request, "https://httpbin.org/response-headers?foo=bar", {}
        )
        assert status == HTTPStatus.OK

    @pytest.mark.parametrize(
        "body, should_decode",
        [(b"test", True), (b"\xff", False)],
    )
    def test__decode_body(self, body, should_decode, manager):
        decoded = manager._decode_body(body=body)
        assert isinstance(decoded, str)

        if should_decode:
            assert decoded == body.decode()
        else:
            assert decoded == str(body)


class TestFilters:
    def test___filter_headers(self, mock_request):
        assert "User-Agent" in mock_request.headers

        _filter = ["User-Agent", ("Accept", "REDACTED"), "Content-Type"]
        filtered_headers = _filter_headers(mock_request.headers, _filter)
        assert "User-Agent" not in filtered_headers
        assert filtered_headers["Accept"] == "REDACTED"

    def test___filter_querystring(self, mock_request):
        assert "foo" in mock_request.querystring

        _filter = ["foo", ("bar", "REDACTED"), "baz"]
        filtered_querystring = _filter_querystring(mock_request.querystring, _filter)
        assert "foo" not in filtered_querystring
        assert filtered_querystring["bar"] == "REDACTED"

    def test__filter_uri(self, mock_request):
        assert "httpbin.org" in mock_request.uri

        _filter = ["status", ("foo", "REDACTED")]
        filtered_uri = _filter_uri(mock_request.uri, _filter)
        assert "status" not in filtered_uri
        assert "foo" not in filtered_uri
        assert "REDACTED" in filtered_uri
