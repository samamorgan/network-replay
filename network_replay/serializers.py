from __future__ import annotations

import json
from typing import TYPE_CHECKING

import yaml

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader

if TYPE_CHECKING:
    from pathlib import Path


class Serializer:
    suffix = None

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


class YAMLSerializer(Serializer):
    suffix = ".yaml"

    def serialize(self, obj) -> None:
        return yaml.dump(obj, self.path.open(mode="w"), Dumper=Dumper)

    def deserialize(self) -> list[dict]:
        return yaml.load(self.path.open(), Loader=Loader)
