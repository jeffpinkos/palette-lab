from __future__ import annotations

from typing import Protocol

from .domain import PaletteColor, PaletteDataset, Recommendation


class PaletteProvider(Protocol):
    id: str

    def load(self) -> PaletteDataset: ...


class RecommendationEngine(Protocol):
    id: str
    name: str

    def fit(self, dataset: PaletteDataset) -> None: ...
    def recommend(self, selected_colors: list[PaletteColor], mode: str, limit: int, scope: str = "palette") -> list[Recommendation]: ...
