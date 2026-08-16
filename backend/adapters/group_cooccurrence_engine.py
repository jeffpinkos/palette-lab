from __future__ import annotations

import math
from typing import Optional

from ..domain import PaletteColor, PaletteDataset, Recommendation


class GroupCooccurrenceEngine:
    """Explainable baseline that learns from any palette's item-to-group matrix."""

    id = "group-cooccurrence-v1"
    name = "Group co-occurrence"

    def __init__(self):
        self._dataset: Optional[PaletteDataset] = None
        self._colors_by_id: dict[str, PaletteColor] = {}

    def fit(self, dataset: PaletteDataset) -> None:
        self._dataset = dataset
        self._colors_by_id = {color.id: color for color in dataset.colors}

    @staticmethod
    def _distance(left: PaletteColor, right: PaletteColor) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(left.rgb, right.rgb))) / 441.67

    def recommend(self, selected_color_ids: list[str], mode: str = "balanced", limit: int = 4) -> list[Recommendation]:
        if self._dataset is None:
            raise RuntimeError("Engine must be fit before inference")
        selected = [self._colors_by_id[color_id] for color_id in selected_color_ids if color_id in self._colors_by_id]
        if not selected:
            return []
        observed = frozenset().union(*(self._dataset.groups_by_color[color.id] for color in selected))
        scored: list[Recommendation] = []
        selected_ids = frozenset(color.id for color in selected)
        for candidate in self._dataset.colors:
            if candidate.id in selected_ids:
                continue
            groups = self._dataset.groups_by_color.get(candidate.id, frozenset())
            shared = len(groups & observed)
            if not shared:
                continue
            co_occurrence = shared / math.sqrt(max(1, len(groups) * len(observed)))
            distance = sum(self._distance(candidate, color) for color in selected) / len(selected)
            mood = 1 - distance if mode == "quiet" else distance if mode == "vivid" else 1 - abs(distance - .52)
            scored.append(Recommendation(candidate, co_occurrence * .82 + mood * .18, "shared", shared))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]
