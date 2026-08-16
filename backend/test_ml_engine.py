import json

import pytest

pytest.importorskip("sklearn")

from .adapters.cluster_ensemble_engine import ClusterEnsembleEngine
from .domain import PaletteColor, PaletteDataset, PaletteMetadata


def clustered_dataset():
    specs = [
        ("r1", (245, 25, 20), ("warm", "strong")), ("r2", (225, 45, 35), ("warm", "strong")),
        ("r3", (250, 80, 50), ("warm", "soft")), ("r4", (205, 30, 60), ("warm", "soft")),
        ("b1", (20, 45, 245), ("cool", "strong")), ("b2", (35, 65, 225), ("cool", "strong")),
        ("b3", (55, 95, 240), ("cool", "soft")), ("b4", (25, 80, 200), ("cool", "soft")),
        ("g1", (20, 220, 70), ("natural", "strong")), ("g2", (45, 200, 85), ("natural", "strong")),
        ("g3", (70, 235, 110), ("natural", "soft")), ("g4", (30, 180, 65), ("natural", "soft")),
    ]
    colors = tuple(PaletteColor(color_id, color_id.upper(), "#%02x%02x%02x" % rgb, rgb) for color_id, rgb, _ in specs)
    groups = {color_id: frozenset(group_ids) for color_id, _, group_ids in specs}
    metadata = PaletteMetadata("clusters", "Clusters", "Fixture", "Tests", None, None, None, "groups")
    return PaletteDataset(metadata, colors, groups, 5)


@pytest.fixture
def trained_engine():
    engine = ClusterEnsembleEngine(random_state=7, min_clusters=2, max_clusters=4)
    engine.fit(clustered_dataset())
    return engine


def test_requires_fit_for_inference():
    with pytest.raises(RuntimeError, match="fit"):
        ClusterEnsembleEngine().recommend([], "balanced", 4)


def test_requires_fit_for_diagnostics():
    with pytest.raises(RuntimeError, match="fit"):
        ClusterEnsembleEngine().diagnostics()


def test_rejects_too_few_colors():
    dataset = clustered_dataset()
    with pytest.raises(ValueError, match="at least four"):
        ClusterEnsembleEngine().fit(PaletteDataset(dataset.metadata, dataset.colors[:3], {}, 0))


def test_evaluates_all_algorithm_families(trained_engine):
    algorithms = {item["algorithm"] for item in trained_engine.diagnostics()["candidates"]}
    assert algorithms == {"kmeans", "agglomerative", "gaussian_mixture"}


def test_evaluates_each_requested_cluster_count(trained_engine):
    counts = {item["clusters"] for item in trained_engine.diagnostics()["candidates"]}
    assert counts == {2, 3, 4}


def test_reports_all_three_quality_metrics(trained_engine):
    candidate = trained_engine.diagnostics()["candidates"][0]
    assert {"silhouette", "calinski_harabasz", "davies_bouldin", "group_recall_at_10", "composite"}.issubset(candidate)


def test_selected_model_is_top_composite(trained_engine):
    diagnostics = trained_engine.diagnostics()
    assert diagnostics["selected"] == diagnostics["candidates"][0]


def test_diagnostics_are_json_serializable(trained_engine):
    assert json.loads(json.dumps(trained_engine.diagnostics()))["engine"]["id"] == "cluster-ensemble-v1"


def test_training_shape_is_reported(trained_engine):
    training = trained_engine.diagnostics()["training"]
    assert training["samples"] == 12
    assert training["groups"] == 5
    assert training["features"] > 3
    assert training["randomState"] == 7
    assert training["colorSpace"] == "OKLab / OKLCH"
    assert "holdout" in training["validation"]


def test_training_is_reproducible():
    left = ClusterEnsembleEngine(random_state=19, min_clusters=2, max_clusters=4)
    right = ClusterEnsembleEngine(random_state=19, min_clusters=2, max_clusters=4)
    left.fit(clustered_dataset())
    right.fit(clustered_dataset())
    assert left.diagnostics()["selected"] == right.diagnostics()["selected"]


def test_recommends_for_known_palette_color(trained_engine):
    results = trained_engine.recommend([clustered_dataset().colors[0]], "balanced", 4)
    assert len(results) == 4
    assert all(result.color.id != "r1" for result in results)


def test_recommends_for_arbitrary_color(trained_engine):
    custom = PaletteColor("custom:#f11919", "Custom", "#f11919", (241, 25, 25))
    results = trained_engine.recommend([custom], "balanced", 4)
    assert len(results) == 4
    assert "r1" not in {result.color.id for result in results}


def test_respects_limit(trained_engine):
    assert len(trained_engine.recommend([clustered_dataset().colors[0]], "balanced", 2)) == 2


def test_empty_selection_returns_empty(trained_engine):
    assert trained_engine.recommend([], "balanced", 4) == []


@pytest.mark.parametrize("mode", ["quiet", "balanced", "vivid"])
def test_all_modes_produce_finite_scores(trained_engine, mode):
    results = trained_engine.recommend([clustered_dataset().colors[0]], mode, 4)
    assert all(0 < result.score <= 1 for result in results)


def test_evidence_exposes_artist_facing_reasons(trained_engine):
    results = trained_engine.recommend([clustered_dataset().colors[0]], "balanced", 4)
    assert all(result.evidence_label in {"shared Wada group", "shared Wada groups", "model affinity"} for result in results)
    assert all(result.evidence_details for result in results)
    assert all("°" in result.evidence_details[0] for result in results)


def test_custom_color_reports_weighted_training_anchors(trained_engine):
    custom = PaletteColor("custom:#f11919", "Custom", "#f11919", (241, 25, 25))
    details = trained_engine.recommend([custom], "balanced", 1)[0].evidence_details
    assert any("interpreted through" in detail for detail in details)


def test_spectrum_scope_generates_continuous_colors(trained_engine):
    results = trained_engine.recommend([clustered_dataset().colors[0]], "balanced", 4, "spectrum")
    assert len(results) == 4
    assert all(result.color.id.startswith("generated:") for result in results)
    assert all(result.color.metadata["generated"] is True for result in results)
    assert all("OKLCH" in result.evidence_details[-1] for result in results)


def test_modes_create_distinct_spectrum_directions(trained_engine):
    selected = [clustered_dataset().colors[0]]
    palettes = {mode: [item.color.hex for item in trained_engine.recommend(selected, mode, 4, "spectrum")] for mode in ("quiet", "balanced", "vivid")}
    assert len({tuple(colors) for colors in palettes.values()}) == 3


def test_diagnostics_weights_include_harmony_retrieval(trained_engine):
    weights = trained_engine.diagnostics()["metricWeights"]
    assert weights["groupRecallAt10"] == .40
    assert sum(weights.values()) == pytest.approx(1)


def test_rgb_only_palette_can_train():
    dataset = clustered_dataset()
    engine = ClusterEnsembleEngine(min_clusters=2, max_clusters=3)
    engine.fit(PaletteDataset(dataset.metadata, dataset.colors, {}, 0))
    assert engine.diagnostics()["training"]["features"] == 3


def test_static_normalization_handles_ties():
    assert ClusterEnsembleEngine._normalized([4.0, 4.0]) == [0.5, 0.5]


def test_static_normalization_can_invert_lower_is_better():
    assert ClusterEnsembleEngine._normalized([1.0, 3.0], lower_is_better=True) == [1.0, 0.0]
