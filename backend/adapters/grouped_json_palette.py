from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..domain import PaletteColor, PaletteDataset, PaletteMetadata


@dataclass(frozen=True)
class JsonFieldMapping:
    collection: str
    id: str
    name: str
    hex: str
    rgb: str
    groups: str


class GroupedJsonPaletteProvider:
    """Normalizes a grouped JSON palette without leaking its source schema downstream."""

    def __init__(
        self,
        path: Path,
        metadata: PaletteMetadata,
        fields: JsonFieldMapping,
        default_color_ids: tuple[str, ...] = (),
    ):
        self.id = metadata.id
        self._path = path
        self._metadata = metadata
        self._fields = fields
        self._default_color_ids = default_color_ids

    def load(self) -> PaletteDataset:
        payload = json.loads(self._path.read_text())
        records = payload[self._fields.collection]
        colors = tuple(PaletteColor(
            id=str(item[self._fields.id]),
            name=re.sub(r"\bBLue\b", "Blue", item[self._fields.name]),
            hex=item[self._fields.hex],
            rgb=tuple(item[self._fields.rgb]),
            metadata={"sourceRecord": item[self._fields.id]},
        ) for item in records)
        groups_by_color = {
            str(item[self._fields.id]): frozenset(str(group) for group in item[self._fields.groups])
            for item in records
        }
        all_groups = frozenset().union(*groups_by_color.values()) if groups_by_color else frozenset()
        return PaletteDataset(self._metadata, colors, groups_by_color, len(all_groups), self._default_color_ids)
