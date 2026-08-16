from __future__ import annotations

from typing import Optional

from ..color_space import perceptual_distance
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
        return perceptual_distance(left.rgb, right.rgb)

    def recommend(self, selected_colors: list[PaletteColor], mode: str = "balanced", limit: int = 4, scope: str = "palette") -> list[Recommendation]:
        if self._dataset is None:
            raise RuntimeError("Engine must be fit before inference")
        if not selected_colors or not self._dataset.colors:
            return []
        anchors = []
        for selected in selected_colors:
            known = self._colors_by_id.get(selected.id)
            anchors.append(known or min(self._dataset.colors, key=lambda candidate: self._distance(selected, candidate)))
        observed = frozenset().union(*(self._dataset.groups_by_color.get(color.id, frozenset()) for color in anchors))
        scored: list[Recommendation] = []
        selected_ids = frozenset(color.id for color in selected_colors) | frozenset(color.id for color in anchors)
        for candidate in self._dataset.colors:
            if candidate.id in selected_ids:
                continue
            groups = self._dataset.groups_by_color.get(candidate.id, frozenset())
            shared = len(groups & observed)
            if not shared:
                continue
            co_occurrence = shared / max(1, (len(groups) * len(observed)) ** 0.5)
            distance = sum(self._distance(candidate, color) for color in selected_colors) / len(selected_colors)
            mood = 1 - distance if mode == "quiet" else distance if mode == "vivid" else 1 - abs(distance - .52)
            noun = "group" if shared == 1 else "groups"
            details = (f"Appears with the selection in {shared} palette {noun}",)
            scored.append(Recommendation(candidate, co_occurrence * .82 + mood * .18, f"shared {noun}", shared, details))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]
