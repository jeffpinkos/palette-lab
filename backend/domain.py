from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class PaletteColor:
    id: str
    name: str
    hex: str
    rgb: tuple[int, int, int]
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "hex": self.hex, "rgb": self.rgb, "metadata": self.metadata}


@dataclass(frozen=True)
class PaletteMetadata:
    id: str
    name: str
    description: str
    source_name: str
    source_url: Optional[str]
    attribution: Optional[str]
    edition_label: Optional[str]
    group_label: str

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "sourceName": self.source_name, "sourceUrl": self.source_url,
            "attribution": self.attribution, "editionLabel": self.edition_label,
            "groupLabel": self.group_label,
        }


@dataclass(frozen=True)
class PaletteDataset:
    metadata: PaletteMetadata
    colors: tuple[PaletteColor, ...]
    groups_by_color: dict[str, frozenset[str]]
    group_count: int
    default_color_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    color: PaletteColor
    score: float
    evidence_label: Optional[str] = None
    evidence_value: Optional[int] = None
    evidence_details: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        evidence = None if self.evidence_label is None else {
            "label": self.evidence_label,
            "value": self.evidence_value,
            "details": self.evidence_details,
        }
        return {"color": self.color.as_dict(), "score": round(self.score, 4), "evidence": evidence}
