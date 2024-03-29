from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from network_replay import ReplayManager
from network_replay.serializers import JSONSerializer

if TYPE_CHECKING:
    from network_replay.serializers import Serializer


@pytest.fixture(autouse=True)
def _replay_marker(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("network_replay"):
        request.getfixturevalue("replay_manager")


@pytest.fixture
def recording_dir() -> str:
    return "recordings"


@pytest.fixture
def replay_recording_path(request: pytest.FixtureRequest, recording_dir: str) -> Path:
    """Path to the recording."""
    test_name = request.node.name
    if request.cls:
        test_name = f"{request.cls.__name__}.{test_name}"

    return Path(request.node.fspath.dirname, recording_dir, f"{test_name}.json")


@pytest.fixture
def replay_record_on_error() -> bool:
    return False


@pytest.fixture
def replay_filter_headers() -> tuple:
    return ()


@pytest.fixture
def replay_filter_querystring() -> tuple:
    return ()


@pytest.fixture
def replay_filter_uri() -> tuple:
    return ()


@pytest.fixture
def replay_serializer() -> JSONSerializer:
    return JSONSerializer


@pytest.fixture
def replay_config(
    replay_recording_path: Path,
    replay_record_on_error: bool,
    replay_filter_headers: tuple,
    replay_filter_querystring: tuple,
    replay_filter_uri: tuple,
    replay_serializer: Serializer,
) -> dict:
    return {
        "path": replay_recording_path,
        "record_on_error": replay_record_on_error,
        "filter_headers": replay_filter_headers,
        "filter_querystring": replay_filter_querystring,
        "filter_uri": replay_filter_uri,
        "serializer": replay_serializer,
    }


@pytest.fixture
def replay_manager(
    replay_config: dict, request: pytest.FixtureRequest
) -> ReplayManager:
    replay_marker = request.node.get_closest_marker("network_replay")
    if replay_marker:
        replay_config.update(replay_marker.kwargs)

    with ReplayManager(**replay_config) as manager:
        yield manager

    try:
        manager.serializer.path.resolve(strict=True)
    except FileNotFoundError as exc:
        pytest.fail(str(exc))
