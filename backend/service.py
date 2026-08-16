from __future__ import annotations

from collections.abc import Callable

from .contracts import PaletteProvider, RecommendationEngine
from .domain import PaletteDataset, Recommendation


class RecommendationService:
    def __init__(self, providers: dict[str, PaletteProvider], engine_factories: dict[str, Callable[[], RecommendationEngine]]):
        self._providers = providers
        self._engine_factories = engine_factories
        self._datasets: dict[str, PaletteDataset] = {}
        self._engines: dict[tuple[str, str], RecommendationEngine] = {}

    @property
    def palette_ids(self) -> tuple[str, ...]:
        return tuple(self._providers)

    @property
    def engine_ids(self) -> tuple[str, ...]:
        return tuple(self._engine_factories)

    def dataset(self, palette_id: str) -> PaletteDataset:
        if palette_id not in self._providers:
            raise KeyError(f"Unknown palette: {palette_id}")
        if palette_id not in self._datasets:
            self._datasets[palette_id] = self._providers[palette_id].load()
        return self._datasets[palette_id]

    def _engine(self, palette_id: str, engine_id: str) -> RecommendationEngine:
        if engine_id not in self._engine_factories:
            raise KeyError(f"Unknown engine: {engine_id}")
        key = (palette_id, engine_id)
        if key not in self._engines:
            engine = self._engine_factories[engine_id]()
            engine.fit(self.dataset(palette_id))
            self._engines[key] = engine
        return self._engines[key]

    def recommend(self, palette_id: str, engine_id: str, color_ids: list[str], mode: str, limit: int) -> list[Recommendation]:
        dataset = self.dataset(palette_id)
        known = {color.id for color in dataset.colors}
        unknown = [color_id for color_id in color_ids if color_id not in known]
        if unknown:
            raise ValueError(f"Unknown color ids: {unknown}")
        return self._engine(palette_id, engine_id).recommend(color_ids, mode, limit)
