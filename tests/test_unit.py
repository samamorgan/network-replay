from __future__ import annotations

import inspect
from contextlib import nullcontext
from http import HTTPStatus
from pathlib import Path
from tempfile import gettempdir
from typing import TYPE_CHECKING

import pytest
import requests
from httpretty.core import SOCKET_GLOBAL_DEFAULT_TIMEOUT

from network_replay import ReplayManager, replay
from network_replay.core import RecordMode, _recording_path
from network_replay.exceptions import RecordingDisabledError
from network_replay.filters import _filter_headers, _filter_querystring, _filter_uri
from network_replay.serializers import JSONSerializer, YAMLSerializer

if TYPE_CHECKING:
    from typing import ContextManager


BASE_PATH = Path(__file__).parent


def _get_200():
    return requests.get("https://httpbin.org/status/200")


@pytest.fixture
def mock_request():
    class MockRequest:
        pass

    request = MockRequest()
    request.uri = "https://httpbin.org"
    request.headers = {"User-Agent": "test", "Accept": "application/json"}
    request.body = b""
    request.method = "GET"
    request.querystring = {"foo": 1, "bar": 2}
    request.timeout = SOCKET_GLOBAL_DEFAULT_TIMEOUT

    return request


@pytest.fixture
def request_json():
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
def path():
    path = Path(gettempdir(), "test")
    yield path
    path.unlink(missing_ok=True)


class TestReplayDecorator:
    @pytest.mark.parametrize(
        "directory",
        ["recordings", "archive"],
    )
    def test_method_directory(self, directory):
        @replay(directory=directory)
        def get_200():
            return _get_200()

        response = get_200()
        assert response.status_code == HTTPStatus.OK
        assert (BASE_PATH / directory / "get_200.json").exists()

    def test_replay_manager_kwargs(self, replay_config):
        @replay(**replay_config)
        def get_manager():
            return inspect.currentframe().f_back.f_locals["_"]

        manager = get_manager()
        assert manager.path.parent == replay_config["path"].parent
        assert manager.path.stem == replay_config["path"].stem
        assert manager.record_on_error == replay_config["record_on_error"]
        assert manager.filter_headers == replay_config["filter_headers"]
        assert manager.filter_querystring == replay_config["filter_querystring"]
        assert manager.filter_uri == replay_config["filter_uri"]
        assert manager.serializer.__class__ == replay_config["serializer"]
        assert manager.record_mode == RecordMode(replay_config["record_mode"])

    def test_class_method_directory(self):
        class Requester:
            @replay
            def get_200(self):
                return _get_200()

        response = Requester().get_200()
        assert response.status_code == HTTPStatus.OK
        assert (BASE_PATH / "recordings" / "Requester.get_200.json").exists()


class TestRecordingPath:
    def test__recording_path_nonlocal(self):
        path = _recording_path(_get_200, "recordings")
        assert "<locals>" not in _get_200.__qualname__
        assert path == BASE_PATH / "recordings" / "_get_200.json"

    def test__recording_path_local(self):
        def get_200():
            pass

        path = _recording_path(get_200, "recordings")
        assert "<locals>" in get_200.__qualname__
        assert path == BASE_PATH / "recordings" / "get_200.json"


class TestReplayManager:
    @pytest.fixture
    def manager(self, path):
        manager = ReplayManager(path=str(path))
        yield manager
        manager.path.unlink(missing_ok=True)

    @pytest.fixture
    def recording(self, manager, request_json):
        manager.serializer.serialize(request_json)

    def test___init__(self, manager):
        assert manager.record_on_error is False
        assert manager.filter_headers == ()
        assert manager.filter_querystring == ()
        assert manager.filter_uri == ()
        assert manager.record_mode == RecordMode.ONCE
        assert manager._cycle_sequence == []

    def test_path(self, manager):
        assert manager.path == manager.serializer.path

    def test_recording_exists(self, manager):
        assert manager.recording_exists is False

        manager.path.touch()
        assert manager.recording_exists is True

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
            m._cycle_sequence.append("test")

        assert m._is_enabled is False
        assert manager.path.exists()

    def test___exit___record_on_error(self, manager):
        with pytest.raises(Exception):
            with manager as m:
                m._cycle_sequence.append("test")
                raise Exception

        assert m._is_enabled is False
        assert not manager.path.exists()

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
        ["body", "should_decode"],
        [(b"test", True), (b"\xff", False)],
    )
    def test__decode_body(self, body, should_decode, manager):
        decoded = manager._decode_body(body=body)
        assert isinstance(decoded, str)

        if should_decode:
            assert decoded == body.decode()
        else:
            assert decoded == str(body)

    @pytest.mark.parametrize(
        ["record_mode", "expectation"],
        [
            (RecordMode.APPEND, nullcontext()),
            (
                RecordMode.BLOCK,
                pytest.raises(RecordingDisabledError, match="Recording is disabled"),
            ),
            (RecordMode.ONCE, nullcontext()),
            (RecordMode.OVERWRITE, nullcontext()),
            (
                RecordMode.REPLAY_ONLY,
                pytest.raises(RecordingDisabledError, match="Recording is disabled"),
            ),
        ],
    )
    def test_record_modes(
        self,
        manager: ReplayManager,
        mock_request,
        record_mode: RecordMode,
        expectation: ContextManager,
    ):
        manager.record_mode = record_mode
        with expectation:
            manager._record_request(mock_request, "https://httpbin.org", {})


class TestFilters:
    def test__filter_headers(self, mock_request):
        assert "User-Agent" in mock_request.headers

        _filter = ["User-Agent", ("Accept", "REDACTED"), "Content-Type"]
        filtered_headers = _filter_headers(mock_request.headers, _filter)
        assert "User-Agent" not in filtered_headers
        assert filtered_headers["Accept"] == "REDACTED"

    def test__filter_querystring(self, mock_request):
        assert "foo" in mock_request.querystring

        _filter = ["foo", ("bar", "REDACTED"), "baz"]
        filtered_querystring = _filter_querystring(mock_request.querystring, _filter)
        assert "foo" not in filtered_querystring
        assert filtered_querystring["bar"] == "REDACTED"

    def test__filter_uri(self, mock_request):
        assert mock_request.uri == "https://httpbin.org"

        _filter = ["bin", ("org", "com"), "baz"]
        filtered_uri = _filter_uri(mock_request.uri, _filter)
        assert "bin" not in filtered_uri
        assert "org" not in filtered_uri
        assert "com" in filtered_uri
        assert filtered_uri.endswith("/")


class SerializerTestBase:
    @pytest.fixture
    def serializer_class(self):
        return None

    @pytest.fixture
    def serializer(self, serializer_class, path):
        serializer = serializer_class(path)
        yield serializer
        serializer.path.unlink(missing_ok=True)

    @pytest.fixture
    def recording(self, serializer, request_json):
        serializer.serialize(request_json)
        yield serializer.path

    def test___init__(self, serializer, serializer_class):
        assert serializer.path.parent.exists()
        assert serializer.path.suffix == serializer_class.suffix

    def test_serialize(self, serializer, request_json):
        assert serializer.path.exists() is False

        result = serializer.serialize(request_json)
        assert result is None
        assert serializer.path.exists() is True

    @pytest.mark.usefixtures("recording")
    def test_deserialize(self, serializer, request_json):
        assert serializer.deserialize() == request_json


class TestJSONSerializer(SerializerTestBase):
    @pytest.fixture
    def serializer_class(self):
        return JSONSerializer


class TestYAMLSerializer(SerializerTestBase):
    @pytest.fixture
    def serializer_class(self):
        return YAMLSerializer
