from __future__ import annotations

from collections.abc import Callable

from .contracts import PaletteProvider, RecommendationEngine
from .domain import PaletteColor, PaletteDataset, Recommendation


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

    def recommend(self, palette_id: str, engine_id: str, selected_colors: list[PaletteColor], mode: str, limit: int, scope: str = "palette") -> list[Recommendation]:
        self.dataset(palette_id)
        return self._engine(palette_id, engine_id).recommend(selected_colors, mode, limit, scope)

    def diagnostics(self, palette_id: str, engine_id: str) -> dict:
        engine = self._engine(palette_id, engine_id)
        diagnostics = getattr(engine, "diagnostics", None)
        return diagnostics() if diagnostics else {"engine": {"id": engine.id, "name": engine.name}, "diagnostics": None}
