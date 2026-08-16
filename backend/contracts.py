from __future__ import annotations

from typing import Protocol

from .domain import PaletteDataset, Recommendation


class PaletteProvider(Protocol):
    id: str

    def load(self) -> PaletteDataset: ...


class RecommendationEngine(Protocol):
    id: str
    name: str

    def fit(self, dataset: PaletteDataset) -> None: ...
    def recommend(self, selected_color_ids: list[str], mode: str, limit: int) -> list[Recommendation]: ...
