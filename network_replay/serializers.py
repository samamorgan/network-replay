from __future__ import annotations

import json
from typing import TYPE_CHECKING

import yaml

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:  # pragma: no cover
    from yaml import Dumper, Loader  # type: ignore[assignment]

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from .types import Transactions


class Serializer:
    suffix: str

    def __init__(self, path: Path) -> None:
        self.path = path.with_suffix(self.suffix)

        self.path.parent.mkdir(exist_ok=True)

    def serialize(self, obj: Transactions) -> None:
        raise NotImplementedError(
            "This method must be overridden by subclasses"
        )  # pragma: no cover

    def deserialize(self) -> Any:
        raise NotImplementedError(
            "This method must be overridden by subclasses"
        )  # pragma: no cover


class JSONSerializer(Serializer):
    suffix = ".json"

    def serialize(self, obj: Transactions) -> None:
        return json.dump(obj, self.path.open(mode="w"), indent=2)

    def deserialize(self) -> Any:
        return json.load(self.path.open())


class YAMLSerializer(Serializer):
    suffix = ".yaml"

    def serialize(self, obj: Transactions) -> None:
        return yaml.dump(obj, self.path.open(mode="w"), Dumper=Dumper)

    def deserialize(self) -> Any:
        return yaml.load(self.path.open(), Loader=Loader)
