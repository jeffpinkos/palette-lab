import json

import pytest

from .adapters.group_cooccurrence_engine import GroupCooccurrenceEngine
from .adapters.grouped_json_palette import GroupedJsonPaletteProvider, JsonFieldMapping
from .domain import PaletteAssessment, PaletteColor, PaletteDataset, PaletteMetadata, Recommendation
from .registry import wada_provider
from .service import RecommendationService


def metadata(palette_id="sample"):
    return PaletteMetadata(palette_id, "Sample", "Test palette", "Fixture", None, None, None, "sets")


def sample_dataset(palette_id="sample"):
    colors = (
        PaletteColor("a", "Red", "#ff0000", (255, 0, 0)),
        PaletteColor("b", "Blue", "#0000ff", (0, 0, 255)),
        PaletteColor("c", "Near red", "#ee1010", (238, 16, 16)),
        PaletteColor("d", "Green", "#00ff00", (0, 255, 0)),
        PaletteColor("e", "Orphan", "#ffffff", (255, 255, 255)),
    )
    groups = {"a": frozenset(("one", "two")), "b": frozenset(("one", "two")), "c": frozenset(("one",)), "d": frozenset(("two",)), "e": frozenset()}
    return PaletteDataset(metadata(palette_id), colors, groups, 2, ("a",))


def selected(dataset, *ids):
    by_id = {color.id: color for color in dataset.colors}
    return [by_id[color_id] for color_id in ids]


@pytest.fixture
def fitted_engine():
    engine = GroupCooccurrenceEngine()
    engine.fit(sample_dataset())
    return engine


class CountingProvider:
    def __init__(self, dataset):
        self.id = dataset.metadata.id
        self.dataset = dataset
        self.loads = 0

    def load(self):
        self.loads += 1
        return self.dataset


class CountingEngine:
    id = "counting"
    name = "Counting engine"
    instances = []

    def __init__(self):
        self.fits = 0
        self.dataset = None
        self.calls = []
        self.assessment_calls = []
        self.__class__.instances.append(self)

    def fit(self, dataset):
        self.fits += 1
        self.dataset = dataset

    def recommend(self, selected_colors, mode, limit, scope="palette"):
        self.calls.append((selected_colors, mode, limit, scope))
        selected_ids = {color.id for color in selected_colors}
        color = next(color for color in self.dataset.colors if color.id not in selected_ids)
        return [Recommendation(color, .5)][:limit]

    def assess(self, selected_colors):
        self.assessment_calls.append(selected_colors)
        return PaletteAssessment("B", 74, "Strong fit", "Fixture assessment", ("Evidence",))


@pytest.fixture(autouse=True)
def reset_counting_engine():
    CountingEngine.instances.clear()


class TestDomainSerialization:
    def test_color_serializes_generic_fields(self):
        color = PaletteColor("x", "X", "#123456", (18, 52, 86), {"source": 12})
        assert color.as_dict() == {"id": "x", "name": "X", "hex": "#123456", "rgb": (18, 52, 86), "metadata": {"source": 12}}

    def test_metadata_uses_frontend_field_names(self):
        result = metadata().as_dict()
        assert result["sourceName"] == "Fixture"
        assert result["groupLabel"] == "sets"
        assert result["sourceUrl"] is None

    def test_recommendation_serializes_evidence(self):
        recommendation = Recommendation(sample_dataset().colors[0], .123456, "shared groups", 3, ("Historic overlap",)).as_dict()
        assert recommendation["score"] == .1235
        assert recommendation["evidence"] == {"label": "shared groups", "value": 3, "details": ("Historic overlap",)}

    def test_recommendation_omits_absent_evidence(self):
        assert Recommendation(sample_dataset().colors[0], .5).as_dict()["evidence"] is None

    def test_palette_assessment_serializes_artist_facing_grade(self):
        assessment = PaletteAssessment("B", 74, "Strong Wada affinity", "Well supported.", ("Historic evidence",)).as_dict()
        assert assessment == {
            "grade": "B", "score": 74, "label": "Strong Wada affinity",
            "summary": "Well supported.", "details": ("Historic evidence",),
        }


class TestGroupedJsonPaletteProvider:
    @pytest.fixture
    def palette_file(self, tmp_path):
        path = tmp_path / "palette.json"
        path.write_text(json.dumps({"swatches": [
            {"key": 1, "label": "One", "value": "#010203", "channels": [1, 2, 3], "sets": [7, 9]},
            {"key": "two", "label": "Two", "value": "#040506", "channels": [4, 5, 6], "sets": []},
        ]}))
        return path

    def provider(self, path):
        return GroupedJsonPaletteProvider(path, metadata(), JsonFieldMapping("swatches", "key", "label", "value", "channels", "sets"), ("1",))

    def test_normalizes_different_field_names(self, palette_file):
        color = self.provider(palette_file).load().colors[0]
        assert (color.id, color.name, color.hex, color.rgb) == ("1", "One", "#010203", (1, 2, 3))

    def test_normalizes_group_ids_to_strings(self, palette_file):
        assert self.provider(palette_file).load().groups_by_color["1"] == frozenset(("7", "9"))

    def test_counts_unique_groups(self, palette_file):
        assert self.provider(palette_file).load().group_count == 2

    def test_preserves_metadata(self, palette_file):
        assert self.provider(palette_file).load().metadata == metadata()

    def test_preserves_default_ids(self, palette_file):
        assert self.provider(palette_file).load().default_color_ids == ("1",)

    def test_records_source_identifier(self, palette_file):
        assert self.provider(palette_file).load().colors[0].metadata == {"sourceRecord": 1}

    def test_empty_collection_is_valid(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text('{"swatches": []}')
        assert self.provider(path).load().group_count == 0
        assert self.provider(path).load().colors == ()

    def test_missing_collection_is_rejected(self, tmp_path):
        path = tmp_path / "wrong.json"
        path.write_text('{"colors": []}')
        with pytest.raises(KeyError):
            self.provider(path).load()

    def test_invalid_json_is_rejected(self, tmp_path):
        path = tmp_path / "invalid.json"
        path.write_text('not-json')
        with pytest.raises(json.JSONDecodeError):
            self.provider(path).load()

    def test_missing_mapped_field_is_rejected(self, tmp_path):
        path = tmp_path / "incomplete.json"
        path.write_text('{"swatches": [{"key": "a"}]}')
        with pytest.raises(KeyError):
            self.provider(path).load()

    def test_same_adapter_accepts_another_schema(self, tmp_path):
        path = tmp_path / "colors.json"
        path.write_text(json.dumps({"colors": [{"id": "x", "name": "X", "hex": "#000000", "rgb": [0, 0, 0], "families": ["dark"]}]}))
        provider = GroupedJsonPaletteProvider(path, metadata(), JsonFieldMapping("colors", "id", "name", "hex", "rgb", "families"))
        assert provider.load().groups_by_color == {"x": frozenset(("dark",))}


class TestGroupCooccurrenceEngine:
    def test_requires_fit(self):
        with pytest.raises(RuntimeError, match="fit"):
            GroupCooccurrenceEngine().recommend([sample_dataset().colors[0]], "balanced", 4)

    def test_publishes_stable_identity(self):
        assert GroupCooccurrenceEngine.id == "group-cooccurrence-v1"
        assert GroupCooccurrenceEngine.name == "Group co-occurrence"

    def test_returns_empty_without_selections(self, fitted_engine):
        assert fitted_engine.recommend([], "balanced", 4) == []

    def test_returns_empty_for_unknown_selections(self, fitted_engine):
        empty = PaletteDataset(metadata(), (), {}, 0)
        fitted_engine.fit(empty)
        assert fitted_engine.recommend([PaletteColor("custom", "Custom", "#123456", (18, 52, 86))], "balanced", 4) == []

    def test_projects_custom_color_to_nearest_anchor(self, fitted_engine):
        custom = PaletteColor("custom:#fd0101", "Custom color", "#fd0101", (253, 1, 1))
        assert len(fitted_engine.recommend([custom], "balanced", 4)) == 3

    def test_excludes_selected_colors(self, fitted_engine):
        ids = {item.color.id for item in fitted_engine.recommend(selected(sample_dataset(), "a", "b"), "balanced", 10)}
        assert not ids & {"a", "b"}

    def test_excludes_colors_without_overlap(self, fitted_engine):
        assert "e" not in {item.color.id for item in fitted_engine.recommend(selected(sample_dataset(), "a"), "balanced", 10)}

    @pytest.mark.parametrize("limit, expected", [(0, 0), (1, 1), (2, 2), (99, 3)])
    def test_respects_limit(self, fitted_engine, limit, expected):
        assert len(fitted_engine.recommend(selected(sample_dataset(), "a"), "balanced", limit)) == expected

    @pytest.mark.parametrize("mode", ["quiet", "balanced", "vivid"])
    def test_all_modes_return_finite_normalized_scores(self, fitted_engine, mode):
        assert all(0 < item.score <= 1 for item in fitted_engine.recommend(selected(sample_dataset(), "a"), mode, 10))

    def test_quiet_favors_near_color(self, fitted_engine):
        ids = [item.color.id for item in fitted_engine.recommend(selected(sample_dataset(), "a"), "quiet", 10)]
        assert ids.index("c") < ids.index("d")

    def test_vivid_favors_distant_color(self, fitted_engine):
        ids = [item.color.id for item in fitted_engine.recommend(selected(sample_dataset(), "a"), "vivid", 10)]
        assert ids.index("d") < ids.index("c")

    def test_evidence_reports_shared_groups(self, fitted_engine):
        result = fitted_engine.recommend(selected(sample_dataset(), "a"), "balanced", 1)[0]
        assert (result.evidence_label, result.evidence_value) == ("shared groups", 2)
        assert result.evidence_details == ("Appears with the selection in 2 palette groups",)

    def test_multiple_selections_union_observed_groups(self, fitted_engine):
        ids = {item.color.id for item in fitted_engine.recommend(selected(sample_dataset(), "c", "d"), "balanced", 10)}
        assert {"a", "b"}.issubset(ids)

    def test_fit_can_replace_the_active_palette(self, fitted_engine):
        other = PaletteDataset(metadata("other"), (PaletteColor("x", "X", "#000000", (0, 0, 0)), PaletteColor("y", "Y", "#ffffff", (255, 255, 255))), {"x": frozenset(("g",)), "y": frozenset(("g",))}, 1)
        fitted_engine.fit(other)
        assert [item.color.id for item in fitted_engine.recommend(selected(other, "x"), "balanced", 4)] == ["y"]

    def test_custom_color_uses_exact_rgb_for_distance(self, fitted_engine):
        custom = PaletteColor("custom:#fe0101", "Custom color", "#fe0101", (254, 1, 1))
        results = fitted_engine.recommend([custom], "quiet", 10)
        scores = {item.color.id: item.score for item in results}
        assert scores["c"] > scores["d"]

    def test_does_not_recommend_custom_colors_nearest_anchor(self, fitted_engine):
        custom = PaletteColor("custom:#fe0101", "Custom color", "#fe0101", (254, 1, 1))
        assert "a" not in {item.color.id for item in fitted_engine.recommend([custom], "balanced", 10)}


class TestRecommendationService:
    def service(self, datasets=None):
        datasets = datasets or [sample_dataset()]
        providers = {dataset.metadata.id: CountingProvider(dataset) for dataset in datasets}
        return RecommendationService(providers, {CountingEngine.id: CountingEngine}), providers

    def test_exposes_registered_ids(self):
        service, _ = self.service()
        assert service.palette_ids == ("sample",)
        assert service.engine_ids == ("counting",)

    def test_loads_palette_lazily(self):
        service, providers = self.service()
        assert providers["sample"].loads == 0
        service.dataset("sample")
        assert providers["sample"].loads == 1

    def test_caches_loaded_palette(self):
        service, providers = self.service()
        assert service.dataset("sample") is service.dataset("sample")
        assert providers["sample"].loads == 1

    def test_rejects_unknown_palette(self):
        service, _ = self.service()
        with pytest.raises(KeyError, match="Unknown palette"):
            service.dataset("missing")

    def test_rejects_unknown_engine(self):
        service, _ = self.service()
        with pytest.raises(KeyError, match="Unknown engine"):
            service.recommend("sample", "missing", selected(sample_dataset(), "a"), "balanced", 4)

    def test_accepts_arbitrary_color(self):
        service, _ = self.service()
        custom = PaletteColor("custom:#123456", "Custom color", "#123456", (18, 52, 86))
        assert service.recommend("sample", "counting", [custom], "balanced", 4)

    def test_fits_engine_once(self):
        service, _ = self.service()
        service.recommend("sample", "counting", selected(sample_dataset(), "a"), "balanced", 4)
        service.recommend("sample", "counting", selected(sample_dataset(), "b"), "quiet", 2)
        assert len(CountingEngine.instances) == 1
        assert CountingEngine.instances[0].fits == 1

    def test_passes_inference_arguments_unchanged(self):
        service, _ = self.service()
        colors = selected(sample_dataset(), "a")
        service.recommend("sample", "counting", colors, "vivid", 7, "spectrum")
        assert CountingEngine.instances[0].calls == [(colors, "vivid", 7, "spectrum")]

    def test_returns_engine_results(self):
        service, _ = self.service()
        result = service.recommend("sample", "counting", selected(sample_dataset(), "a"), "balanced", 4)
        assert result[0].score == .5
        assert result[0].color.id == "b"

    def test_returns_optional_engine_assessment(self):
        service, _ = self.service()
        colors = selected(sample_dataset(), "a", "b")
        assessment = service.assess("sample", "counting", colors)
        assert (assessment.grade, assessment.score) == ("B", 74)
        assert CountingEngine.instances[0].assessment_calls == [colors]

    def test_caches_separate_engine_per_palette(self):
        service, _ = self.service([sample_dataset("one"), sample_dataset("two")])
        service.recommend("one", "counting", selected(sample_dataset("one"), "a"), "balanced", 4)
        service.recommend("two", "counting", selected(sample_dataset("two"), "a"), "balanced", 4)
        assert len(CountingEngine.instances) == 2
        assert {engine.dataset.metadata.id for engine in CountingEngine.instances} == {"one", "two"}

    def test_zero_limit_returns_no_results(self):
        service, _ = self.service()
        assert service.recommend("sample", "counting", selected(sample_dataset(), "a"), "balanced", 0) == []


def test_wada_provider_and_engine_are_independent():
    service = RecommendationService({wada_provider.id: wada_provider}, {GroupCooccurrenceEngine.id: GroupCooccurrenceEngine})
    dataset = wada_provider.load()
    recommendations = service.recommend("wada-1933", GroupCooccurrenceEngine.id, selected(dataset, "19", "112"), "balanced", 4)
    assert len(recommendations) == 4
    assert not {"19", "112"} & {item.color.id for item in recommendations}
    assert all(item.evidence_value and item.evidence_value > 0 for item in recommendations)


def test_real_wada_provider_reports_expected_shape():
    dataset = wada_provider.load()
    assert len(dataset.colors) == 157
    assert dataset.group_count > 300
    assert dataset.metadata.id == "wada-1933"
    assert dataset.default_color_ids == ("19", "112")
