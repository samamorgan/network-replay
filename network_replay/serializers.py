from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class Serializer:
    suffix = ".txt"

    def __init__(self, path: Path) -> None:
        self.path = path.with_suffix(self.suffix)

        self.path.parent.mkdir(exist_ok=True)

    def serialize(self, obj):
        raise NotImplementedError(
            "This method must be overridden by subclasses"
        )  # pragma: no cover

    def deserialize(self):
        raise NotImplementedError(
            "This method must be overridden by subclasses"
        )  # pragma: no cover


class JSONSerializer(Serializer):
    suffix = ".json"

    def serialize(self, obj) -> None:
        return json.dump(obj, self.path.open(mode="w"), indent=2)

    def deserialize(self) -> list[dict]:
        return json.load(self.path.open())
