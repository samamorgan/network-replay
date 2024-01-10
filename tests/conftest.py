from pathlib import Path

import pytest

from network_replay import ReplayManager

RECORDING_PATH = pytest.StashKey[Path]()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> None:
    output = yield

    if not item.get_closest_marker("network_replay"):
        return

    ReplayManager.disable()
    if output.excinfo is not None:
        return

    try:
        item.stash[RECORDING_PATH].resolve(strict=True)
    except FileNotFoundError as exc:
        pytest.fail(str(exc))


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

    path = Path(request.node.fspath.dirname, recording_dir, f"{test_name}.json")
    request.node.stash[RECORDING_PATH] = path

    return path


@pytest.fixture
def replay_manager(
    recording_path: Path, request: pytest.FixtureRequest
) -> ReplayManager:
    kwargs = {"path": recording_path}
    replay_marker = request.node.get_closest_marker("network_replay")
    if replay_marker:
        kwargs.update(replay_marker.kwargs)

    with ReplayManager(**kwargs) as recorder:
        yield recorder
