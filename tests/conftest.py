from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from network_replay import ReplayManager
from network_replay.core import RecordMode
from network_replay.serializers import JSONSerializer

if TYPE_CHECKING:
    from typing import Iterator

    from network_replay.serializers import Serializer
    from network_replay.types import Filter, ReplayConfig


@pytest.fixture(autouse=True)
def _replay_marker(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("network_replay"):
        request.getfixturevalue("replay_manager")


@pytest.fixture
def recording_dir() -> str:
    return "recordings"


@pytest.fixture
def recording_path(request: pytest.FixtureRequest, recording_dir: str) -> Path:
    """Path to the recording."""
    test_name = request.node.name
    if request.cls:
        test_name = f"{request.cls.__name__}.{test_name}"

    return Path(request.node.fspath.dirname, recording_dir, f"{test_name}.json")


@pytest.fixture
def record_on_error() -> bool:
    return False


@pytest.fixture
def filter_headers() -> Filter:
    return {}


@pytest.fixture
def filter_querystring() -> Filter:
    return {}


@pytest.fixture
def filter_uri() -> Filter:
    return {}


@pytest.fixture
def serializer() -> type[JSONSerializer]:
    return JSONSerializer


@pytest.fixture
def record_mode() -> RecordMode:
    return RecordMode.ONCE


@pytest.fixture
def replay_config(
    recording_path: Path,
    record_on_error: bool,
    filter_headers: Filter,
    filter_querystring: Filter,
    filter_uri: Filter,
    serializer: type[Serializer],
    record_mode: RecordMode,
) -> ReplayConfig:
    return {
        "path": recording_path,
        "record_on_error": record_on_error,
        "filter_headers": filter_headers,
        "filter_querystring": filter_querystring,
        "filter_uri": filter_uri,
        "serializer": serializer,
        "record_mode": record_mode,
    }


@pytest.fixture
def _replay_manager(
    replay_config: ReplayConfig, request: pytest.FixtureRequest
) -> ReplayManager:
    replay_marker = request.node.get_closest_marker("network_replay")
    if replay_marker:
        replay_config.update(replay_marker.kwargs)

    return ReplayManager(**replay_config)


@pytest.fixture
def replay_manager(
    _replay_manager: ReplayManager,
) -> Iterator[ReplayManager]:
    with _replay_manager as manager:
        yield manager

    if manager._transactions:
        try:
            manager.path.resolve(strict=True)
        except FileNotFoundError as exc:
            pytest.fail(str(exc))
