import json

from .adapters.group_cooccurrence_engine import GroupCooccurrenceEngine
from .adapters.grouped_json_palette import GroupedJsonPaletteProvider, JsonFieldMapping
from .domain import PaletteMetadata
from .registry import wada_provider
from .service import RecommendationService


def test_wada_provider_and_engine_are_independent():
    service = RecommendationService({wada_provider.id: wada_provider}, {GroupCooccurrenceEngine.id: GroupCooccurrenceEngine})
    recommendations = service.recommend("wada-1933", GroupCooccurrenceEngine.id, ["19", "112"], "balanced", 4)
    assert len(recommendations) == 4
    assert not {"19", "112"} & {item.color.id for item in recommendations}
    assert all(item.evidence_value and item.evidence_value > 0 for item in recommendations)


def test_same_engine_accepts_another_palette_schema(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text(json.dumps({"swatches": [
        {"key": "a", "label": "A", "value": "#ff0000", "channels": [255, 0, 0], "sets": [1]},
        {"key": "b", "label": "B", "value": "#0000ff", "channels": [0, 0, 255], "sets": [1, 2]},
        {"key": "c", "label": "C", "value": "#00ff00", "channels": [0, 255, 0], "sets": [2]},
    ]}))
    provider = GroupedJsonPaletteProvider(
        path,
        PaletteMetadata("sample", "Sample", "Test", "Fixture", None, None, None, "sets"),
        JsonFieldMapping("swatches", "key", "label", "value", "channels", "sets"),
    )
    service = RecommendationService({"sample": provider}, {GroupCooccurrenceEngine.id: GroupCooccurrenceEngine})
    results = service.recommend("sample", GroupCooccurrenceEngine.id, ["a"], "balanced", 2)
    assert [item.color.id for item in results] == ["b"]
