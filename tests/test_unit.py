from __future__ import annotations

import inspect
from contextlib import nullcontext
from http import HTTPStatus
from pathlib import Path
from tempfile import gettempdir
from typing import TYPE_CHECKING

import pytest
import requests
from httpretty.core import HTTPrettyRequest, fakesock  # type: ignore[import-untyped]

from network_replay import ReplayManager, replay
from network_replay.core import RecordMode, _recording_path
from network_replay.exceptions import RecordingDisabledError
from network_replay.filters import _filter_headers, _filter_querystring, _filter_uri
from network_replay.serializers import JSONSerializer, YAMLSerializer

if TYPE_CHECKING:
    from typing import Any, ContextManager, Iterator

    from network_replay.serializers import Serializer
    from network_replay.types import ReplayConfig, Transactions


def _get_200() -> requests.Response:
    return requests.get("https://httpbin.org/status/200")


@pytest.fixture
def mock_request() -> HTTPrettyRequest:
    sock = fakesock.socket()
    sock.is_http = True

    return HTTPrettyRequest(
        headers="\r\n".join(
            (
                "GET /?foo=1&bar=2 HTTP/1.1",
                "Host: httpbin.org",
                "Accept: application/json",
                "Connection: keep-alive",
                "User-Agent: test",
            )
        ).encode(),
        sock=sock,
    )


@pytest.fixture
def transactions() -> Transactions:
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
def base_path() -> Path:
    return Path(__file__).parent


@pytest.fixture
def path() -> Iterator[Path]:
    path = Path(gettempdir(), "test")
    yield path
    path.unlink(missing_ok=True)


class TestReplayDecorator:
    @pytest.mark.parametrize(
        "directory",
        ["recordings", "archive"],
    )
    def test_method_directory(self, directory: str, base_path: Path) -> None:
        @replay(directory=directory)
        def get_200() -> requests.Response:
            return _get_200()

        response = get_200()
        assert response.status_code == HTTPStatus.OK
        assert (base_path / directory / "get_200.json").exists()

    def test_replay_manager_kwargs(self, replay_config: ReplayConfig) -> None:
        @replay(**replay_config)
        def get_manager() -> ReplayManager:
            return inspect.currentframe().f_back.f_locals["_"]  # type: ignore

        manager = get_manager()
        assert manager.path.parent == replay_config["path"].parent
        assert manager.path.stem == replay_config["path"].stem
        assert manager.record_on_error == replay_config["record_on_error"]
        assert manager.filter_headers == replay_config["filter_headers"]
        assert manager.filter_querystring == replay_config["filter_querystring"]
        assert manager.filter_uri == replay_config["filter_uri"]
        assert manager.serializer.__class__ == replay_config["serializer"]
        assert manager.record_mode == RecordMode(replay_config["record_mode"])

    def test_class_method_directory(self, base_path: Path) -> None:
        class Requester:
            @replay
            def get_200(self) -> requests.Response:
                return _get_200()

        response = Requester().get_200()  # type: ignore[misc]
        assert response.status_code == HTTPStatus.OK  # type: ignore[attr-defined]
        assert (base_path / "recordings" / "Requester.get_200.json").exists()


class TestRecordingPath:
    def test__recording_path_nonlocal(self, base_path: Path) -> None:
        path = _recording_path(_get_200, "recordings")
        assert "<locals>" not in _get_200.__qualname__
        assert path == base_path / "recordings" / "_get_200.json"

    def test__recording_path_local(self, base_path: Path) -> None:
        def get_200() -> None:
            pass

        path = _recording_path(get_200, "recordings")
        assert "<locals>" in get_200.__qualname__
        assert path == base_path / "recordings" / "get_200.json"


class TestReplayManager:
    @pytest.fixture
    def manager(self, path: Path) -> Iterator[ReplayManager]:
        manager = ReplayManager(path=path)
        yield manager
        manager.path.unlink(missing_ok=True)

    @pytest.fixture
    def recording(self, manager: ReplayManager, transactions: Transactions) -> None:
        manager.serializer.serialize(transactions)

    def test___init__(self, manager: ReplayManager) -> None:
        assert manager.record_on_error is False
        assert manager.filter_headers == {}
        assert manager.filter_querystring == {}
        assert manager.filter_uri == {}
        assert manager.record_mode == RecordMode.ONCE
        assert manager._transactions == []

    def test_path(self, manager: ReplayManager) -> None:
        assert manager.path == manager.serializer.path

    def test_recording_exists(self, manager: ReplayManager) -> None:
        assert manager.recording_exists is False

        manager.path.touch()
        assert manager.recording_exists is True

    def test___str__(self, manager: ReplayManager) -> None:
        assert str(manager) == "<ReplayManager with 0 URI entries>"

    @pytest.mark.usefixtures("recording")
    def test___enter__replay(self, manager: ReplayManager) -> None:
        with manager as m:
            assert m.allow_net_connect is False
            assert m._is_enabled is True

    def test___enter__record(self, manager: ReplayManager) -> None:
        with manager as m:
            assert m.allow_net_connect is True
            assert m._is_enabled is True

    def test___exit___replay(self, manager: ReplayManager) -> None:
        with manager as m:
            pass

        assert m._is_enabled is False

    def test___exit___record(
        self, manager: ReplayManager, transactions: Transactions
    ) -> None:
        with manager as m:
            m._transactions.append(transactions[0])

        assert m._is_enabled is False
        assert manager.path.exists()

    def test___exit___record_on_error(
        self, manager: ReplayManager, transactions: Transactions
    ) -> None:
        with pytest.raises(Exception):
            with manager as m:
                m._transactions.append(transactions[0])
                raise Exception

        assert m._is_enabled is False
        assert not manager.path.exists()

    @pytest.mark.usefixtures("recording")
    def test__register_recorded_requests(
        self, manager: ReplayManager, transactions: Transactions
    ) -> None:
        manager._register_recorded_requests()
        assert len(manager._entries) == len(transactions)

    def test__record_request(
        self, manager: ReplayManager, mock_request: HTTPrettyRequest
    ) -> None:
        status, *_ = manager._record_request(
            mock_request, "https://httpbin.org/response-headers?foo=bar", {}
        )
        assert status == HTTPStatus.OK

    @pytest.mark.parametrize(
        ["body", "should_decode"],
        [(b"test", True), (b"\xff", False)],
    )
    def test__decode_body(
        self, manager: ReplayManager, body: bytes, should_decode: bool
    ) -> None:
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
        mock_request: HTTPrettyRequest,
        record_mode: RecordMode,
        expectation: ContextManager[Any],
    ) -> None:
        manager.record_mode = record_mode
        with expectation:
            manager._record_request(mock_request, "https://httpbin.org", {})


class TestReplayURIMatcher:
    pass


class TestFilters:
    def test__filter_headers(self, mock_request: HTTPrettyRequest) -> None:
        assert "User-Agent" in mock_request.headers

        _filter = {"User-Agent": None, "Accept": "REDACTED", "Content-Type": None}
        filtered_headers = _filter_headers(mock_request.headers, _filter)
        assert "User-Agent" not in filtered_headers
        assert filtered_headers["Accept"] == "REDACTED"

    def test__filter_querystring(self, mock_request: HTTPrettyRequest) -> None:
        assert "foo" in mock_request.querystring

        _filter = {"foo": None, "bar": "REDACTED", "baz": None}
        filtered_querystring = _filter_querystring(mock_request.querystring, _filter)
        assert "foo" not in filtered_querystring
        assert filtered_querystring["bar"] == _filter["bar"]

    def test__filter_uri(self, mock_request: HTTPrettyRequest) -> None:
        _filter = {"bin": None, "org": "com", "baz": None}
        filtered_uri = _filter_uri(mock_request.url, _filter)
        assert "bin" not in filtered_uri
        assert "org" not in filtered_uri
        assert "com" in filtered_uri
        assert filtered_uri.endswith("/")


class SerializerTestBase:
    @pytest.fixture
    def serializer_class(self) -> type[Serializer]:
        return Serializer

    @pytest.fixture
    def serializer(
        self, serializer_class: type[Serializer], path: Path
    ) -> Iterator[Serializer]:
        serializer = serializer_class(path)
        yield serializer
        serializer.path.unlink(missing_ok=True)

    @pytest.fixture
    def recording(
        self, serializer: Serializer, transactions: Transactions
    ) -> Iterator[Path]:
        serializer.serialize(transactions)
        yield serializer.path

    def test___init__(
        self, serializer: Serializer, serializer_class: type[Serializer]
    ) -> None:
        assert serializer.path.parent.exists()
        assert serializer.path.suffix == serializer_class.suffix

    def test_serialize(
        self, serializer: Serializer, transactions: Transactions
    ) -> None:
        assert serializer.path.exists() is False

        serializer.serialize(transactions)
        assert serializer.path.exists() is True

    @pytest.mark.usefixtures("recording")
    def test_deserialize(
        self, serializer: Serializer, transactions: Transactions
    ) -> None:
        assert serializer.deserialize() == transactions


class TestJSONSerializer(SerializerTestBase):
    @pytest.fixture
    def serializer_class(self) -> type[JSONSerializer]:
        return JSONSerializer


class TestYAMLSerializer(SerializerTestBase):
    @pytest.fixture
    def serializer_class(self) -> type[YAMLSerializer]:
        return YAMLSerializer
