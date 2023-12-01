from pathlib import Path

import pytest

base_path = Path(__file__).parent


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> None:
    output = yield

    if item.get_closest_marker("recording_check") is None:
        return

    if output.excinfo is not None:
        return

    try:
        (base_path / "recordings" / f"{item.name}.json").resolve(strict=True)
    except FileNotFoundError as exc:
        pytest.fail(str(exc))
