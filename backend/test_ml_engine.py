import json
import math

import numpy as np
import pytest

pytest.importorskip("sklearn")

from .adapters.cluster_ensemble_engine import ClusterEnsembleEngine
from .domain import PaletteColor, PaletteDataset, PaletteMetadata
from .registry import wada_provider


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


@pytest.fixture(scope="module")
def wada_engine():
    engine = ClusterEnsembleEngine(random_state=42)
    engine.fit(wada_provider.load())
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
    assert {"silhouette", "calinski_harabasz", "davies_bouldin", "group_recall_at_10", "group_ndcg_at_10", "composite"}.issubset(candidate)


def test_selected_model_is_top_composite(trained_engine):
    diagnostics = trained_engine.diagnostics()
    assert diagnostics["selected"] == diagnostics["candidates"][0]


def test_diagnostics_are_json_serializable(trained_engine):
    assert json.loads(json.dumps(trained_engine.diagnostics()))["engine"]["id"] == "cluster-ensemble-v2"


def test_training_shape_is_reported(trained_engine):
    training = trained_engine.diagnostics()["training"]
    assert training["samples"] == 12
    assert training["groups"] == 5
    assert training["features"] > 3
    assert training["randomState"] == 7
    assert training["colorSpace"] == "OKLab / OKLCH"
    assert "holdout" in training["validation"]
    assert "TF-IDF" in training["featureDesign"]
    assert "rotation-equivariant" in training["featureDesign"]
    assert "four-neighbor" in training["anchorProjection"]
    assert "determinantal" in training["paletteSelection"]


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
    assert all(result.color.metadata["gamutMapped"] is True for result in results)
    assert all("OKLCH" in result.evidence_details[-1] for result in results)


def test_modes_create_distinct_spectrum_directions(trained_engine):
    selected = [clustered_dataset().colors[0]]
    palettes = {mode: [item.color.hex for item in trained_engine.recommend(selected, mode, 4, "spectrum")] for mode in ("quiet", "balanced", "vivid")}
    assert len({tuple(colors) for colors in palettes.values()}) == 3


def test_diagnostics_weights_include_harmony_retrieval(trained_engine):
    weights = trained_engine.diagnostics()["metricWeights"]
    assert weights["groupRecallAt10"] == .30
    assert weights["groupNdcgAt10"] == .25
    assert weights["parsimony"] == .05
    assert sum(weights.values()) == pytest.approx(1)


def test_rgb_only_palette_can_train():
    dataset = clustered_dataset()
    engine = ClusterEnsembleEngine(min_clusters=2, max_clusters=3)
    engine.fit(PaletteDataset(dataset.metadata, dataset.colors, {}, 0))
    assert engine.diagnostics()["training"]["features"] == 3


def test_perceptual_features_validate_oklab_shape():
    with pytest.raises(ValueError, match="shape"):
        ClusterEnsembleEngine._perceptual_features(np.zeros((4, 2)))


def test_perceptual_features_remain_finite_for_constant_colors():
    features = ClusterEnsembleEngine._perceptual_features(np.repeat([[0.5, 0.0, 0.0]], 4, axis=0))
    assert features == pytest.approx(np.zeros((4, 3)))


@pytest.mark.parametrize("degrees", [1, 30, 73, 120, 179, 359])
def test_perceptual_feature_shape_rotates_equivariantly(degrees):
    labs = np.asarray([
        [0.25, 0.18, 0.02], [0.42, -0.07, 0.16], [0.58, -0.14, -0.08],
        [0.73, 0.05, -0.19], [0.88, 0.11, 0.09],
    ])
    angle = math.radians(degrees)
    rotation = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    rotated_labs = labs.copy()
    rotated_labs[:, 1:] = labs[:, 1:] @ rotation.T
    original = ClusterEnsembleEngine._perceptual_features(labs)
    rotated = ClusterEnsembleEngine._perceptual_features(rotated_labs)
    expected = original.copy()
    expected[:, 1:] = original[:, 1:] @ rotation.T
    assert rotated == pytest.approx(expected, abs=1e-12)


def test_perceptual_pairwise_geometry_is_rotation_invariant():
    rng = np.random.default_rng(91)
    labs = rng.normal(size=(20, 3)) * np.asarray([0.2, 0.1, 0.1]) + np.asarray([0.6, 0.0, 0.0])
    angle = math.radians(137)
    rotation = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    rotated_labs = labs.copy()
    rotated_labs[:, 1:] = labs[:, 1:] @ rotation.T
    original = ClusterEnsembleEngine._perceptual_features(labs)
    rotated = ClusterEnsembleEngine._perceptual_features(rotated_labs)
    distances = lambda values: np.linalg.norm(values[:, None, :] - values[None, :, :], axis=2)
    assert distances(rotated) == pytest.approx(distances(original), abs=1e-12)


@pytest.mark.parametrize("algorithm", ["kmeans", "agglomerative", "gaussian_mixture"])
def test_cluster_families_preserve_comembership_after_rotation(algorithm):
    rng = np.random.default_rng(123)
    centers = np.asarray([[0.35, 0.16, 0.02], [0.62, -0.10, 0.15], [0.78, -0.08, -0.15]])
    labs = np.vstack([center + rng.normal(0, [0.015, 0.012, 0.012], size=(8, 3)) for center in centers])
    historical = np.repeat(np.eye(3), 8, axis=0)
    angle = math.radians(73)
    rotation = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    rotated_labs = labs.copy()
    rotated_labs[:, 1:] = labs[:, 1:] @ rotation.T
    original = np.hstack((ClusterEnsembleEngine._perceptual_features(labs), historical))
    rotated = np.hstack((ClusterEnsembleEngine._perceptual_features(rotated_labs), historical))
    engine = ClusterEnsembleEngine(random_state=42)
    original_labels = engine._candidate_labels(algorithm, 3, original)
    rotated_labels = engine._candidate_labels(algorithm, 3, rotated)
    assert (original_labels[:, None] == original_labels[None, :]).tolist() == (
        rotated_labels[:, None] == rotated_labels[None, :]
    ).tolist()


def test_percentile_ranks_handle_ties():
    assert ClusterEnsembleEngine._percentile_ranks([4.0, 4.0]) == [0.5, 0.5]


def test_percentile_ranks_can_invert_lower_is_better():
    assert ClusterEnsembleEngine._percentile_ranks([1.0, 3.0], lower_is_better=True) == [1.0, 0.0]


def test_percentile_ranks_are_not_distorted_by_outlier_magnitude():
    assert ClusterEnsembleEngine._percentile_ranks([1.0, 2.0, 1_000_000.0]) == [0.0, 0.5, 1.0]


def test_soft_cluster_memberships_are_probability_vectors(trained_engine):
    memberships = trained_engine._cluster_memberships
    assert memberships.shape == (12, trained_engine.diagnostics()["selected"]["clusters"])
    assert (memberships >= 0).all()
    assert (memberships <= 1).all()
    assert memberships.sum(axis=1) == pytest.approx([1.0] * 12)


def test_soft_cluster_memberships_reject_nonpositive_temperature(trained_engine):
    with pytest.raises(ValueError, match="temperature"):
        trained_engine._soft_memberships(trained_engine._features, trained_engine._labels, 0)


def test_lower_temperature_produces_sharper_memberships(trained_engine):
    sharp = trained_engine._soft_memberships(trained_engine._features, trained_engine._labels, 0.25)
    soft = trained_engine._soft_memberships(trained_engine._features, trained_engine._labels, 1.0)
    sharp_entropy = -np.sum(np.where(sharp > 0, sharp * np.log(sharp), 0), axis=1).mean()
    soft_entropy = -np.sum(np.where(soft > 0, soft * np.log(soft), 0), axis=1).mean()
    assert sharp_entropy < soft_entropy


def test_ensemble_keeps_one_calibrated_member_per_family(trained_engine):
    diagnostics = trained_engine.diagnostics()
    members = diagnostics["ensemble"]["members"]
    assert {member["algorithm"] for member in members} == {"kmeans", "agglomerative", "gaussian_mixture"}
    assert diagnostics["ensemble"]["primary"] == {
        "algorithm": diagnostics["selected"]["algorithm"],
        "clusters": diagnostics["selected"]["clusters"],
    }
    assert all(member["membershipTemperatureScale"] in {0.0625, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0} for member in members)
    assert all(0 <= member["softGroupNdcgAt10"] <= 1 for member in members)


def test_each_ensemble_membership_is_a_probability_vector(trained_engine):
    assert len(trained_engine._family_memberships) == 3
    for memberships in trained_engine._family_memberships.values():
        assert memberships.shape[0] == len(clustered_dataset().colors)
        assert memberships.sum(axis=1) == pytest.approx([1.0] * len(clustered_dataset().colors))


def test_recommendations_explain_model_and_historical_fit(trained_engine):
    result = trained_engine.recommend([clustered_dataset().colors[0]], "balanced", 1)[0]
    assert "harmony fit" in result.evidence_details[0]
    assert "model rank agreement" in result.evidence_details[1]
    assert "historic" in result.evidence_details[1]
    assert any(name in result.evidence_details[1] for name in ("support", "contrast"))


@pytest.mark.parametrize("scope", ["palette", "spectrum"])
def test_recommendation_score_weights_are_normalized(scope):
    weights = ClusterEnsembleEngine._score_weights(scope)
    assert set(weights) == {"group", "cluster", "proximity", "mood", "relation", "harmony"}
    assert sum(weights.values()) == pytest.approx(1)
    assert weights["relation"] == 0.10
    assert weights["harmony"] > weights["relation"]


@pytest.mark.parametrize(("degrees", "expected"), [
    (0, "monochromatic"),
    (30, "analogous"),
    (90, "tetradic"),
    (120, "triadic"),
    (150, "split-complementary"),
    (180, "complementary"),
])
def test_classical_harmony_targets_are_recognized(degrees, expected):
    engine = ClusterEnsembleEngine()
    score, name, detail = engine._harmony_fit(
        (0.6, 0.15, degrees), np.asarray([[0.5, 0.15, 0.0]]), "balanced",
    )
    assert name == expected
    assert score >= 0.69
    assert expected.replace("-", " ") in detail
    assert "harmony fit" in detail


def test_harmony_hue_distance_wraps_around_color_wheel():
    engine = ClusterEnsembleEngine()
    score, name, _ = engine._harmony_fit(
        (0.6, 0.15, 170.0), np.asarray([[0.5, 0.15, 350.0]]), "vivid",
    )
    assert name == "complementary"
    assert score == pytest.approx(1)


@pytest.mark.parametrize("mode", ["quiet", "balanced", "vivid"])
def test_classical_harmony_score_is_rotation_invariant(mode):
    engine = ClusterEnsembleEngine()
    candidate = (0.62, 0.16, 137.0)
    selected = np.asarray([[0.48, 0.14, 17.0], [0.73, 0.12, 287.0]])
    score, name, _ = engine._harmony_fit(candidate, selected, mode)
    rotation = 83.0
    rotated_candidate = (candidate[0], candidate[1], (candidate[2] + rotation) % 360)
    rotated_selected = selected.copy()
    rotated_selected[:, 2] = (rotated_selected[:, 2] + rotation) % 360
    rotated_score, rotated_name, _ = engine._harmony_fit(rotated_candidate, rotated_selected, mode)
    assert rotated_score == pytest.approx(score, abs=1e-12)
    assert rotated_name == name


def test_modes_emphasize_different_classical_harmonies():
    engine = ClusterEnsembleEngine()
    selected = np.asarray([[0.5, 0.15, 0.0]])
    quiet_mono = engine._harmony_fit((0.6, 0.15, 0.0), selected, "quiet")[0]
    vivid_mono = engine._harmony_fit((0.6, 0.15, 0.0), selected, "vivid")[0]
    quiet_complement = engine._harmony_fit((0.6, 0.15, 180.0), selected, "quiet")[0]
    vivid_complement = engine._harmony_fit((0.6, 0.15, 180.0), selected, "vivid")[0]
    assert quiet_mono > vivid_mono
    assert vivid_complement > quiet_complement


def test_neutral_colors_use_tonal_harmony_instead_of_unstable_hue():
    engine = ClusterEnsembleEngine()
    score, name, detail = engine._harmony_fit(
        (0.72, 0.01, 280.0), np.asarray([[0.45, 0.15, 20.0]]), "balanced",
    )
    assert name == "tonal"
    assert 0 < score <= 1
    assert "tonal harmony fit" in detail
    assert "°" not in detail


def test_harmony_diagnostics_publish_targets_and_mode_emphasis(trained_engine):
    diagnostics = trained_engine.diagnostics()["harmonyModel"]
    assert diagnostics["colorSpace"] == "OKLCH"
    assert {scheme["name"] for scheme in diagnostics["schemes"]} == {
        "monochromatic", "analogous", "tetradic", "triadic",
        "split-complementary", "complementary",
    }
    assert set(diagnostics["modeEmphasis"]) == {"quiet", "balanced", "vivid"}


def test_relation_fit_is_bounded(trained_engine):
    dataset = clustered_dataset()
    candidate, selected = dataset.colors[:2]
    fit, name = trained_engine._relation_fit(
        candidate_lab=tuple(trained_engine._oklab_matrix[0]),
        candidate_lch=tuple(trained_engine._oklch_matrix[0]),
        selected_labs=np.asarray([trained_engine._oklab_matrix[1]]),
        selected_lch=np.asarray([trained_engine._oklch_matrix[1]]),
    )
    assert 0 <= fit <= 1
    assert name in {"support", "contrast"}


def test_historical_relation_vector_is_rotation_invariant():
    left_lab = np.asarray([0.45, 0.13, -0.04])
    right_lab = np.asarray([0.72, -0.08, 0.17])
    left_lch = np.asarray([0.45, 0.136, 342.9])
    right_lch = np.asarray([0.72, 0.188, 115.2])
    original = ClusterEnsembleEngine._relation_vector(left_lab, left_lch, right_lab, right_lch)
    angle = math.radians(61)
    rotation = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    rotated_left_lab = left_lab.copy()
    rotated_right_lab = right_lab.copy()
    rotated_left_lab[1:] = left_lab[1:] @ rotation.T
    rotated_right_lab[1:] = right_lab[1:] @ rotation.T
    rotated_left_lch = left_lch.copy()
    rotated_right_lch = right_lch.copy()
    rotated_left_lch[2] = (left_lch[2] + 61) % 360
    rotated_right_lch[2] = (right_lch[2] + 61) % 360
    rotated = ClusterEnsembleEngine._relation_vector(
        rotated_left_lab, rotated_left_lch, rotated_right_lab, rotated_right_lch,
    )
    assert rotated == pytest.approx(original, abs=1e-12)


def test_wada_selects_rotation_equivariant_kmeans_10_as_primary(wada_engine):
    selected = wada_engine.diagnostics()["selected"]
    assert (selected["algorithm"], selected["clusters"]) == ("kmeans", 10)
    assert selected["membership_temperature_scale"] == 0.0625
    assert selected["soft_group_ndcg_at_10"] > 0


def test_wada_relation_mixture_learns_support_and_contrast(wada_engine):
    mixture = wada_engine.diagnostics()["relationMixture"]
    support, contrast = mixture["archetypes"]
    assert mixture["pairCount"] == 996
    assert support["name"] == "support"
    assert contrast["name"] == "contrast"
    assert support["weight"] == pytest.approx(0.70, abs=0.01)
    assert contrast["weight"] == pytest.approx(0.30, abs=0.01)
    assert sum(item["weight"] for item in mixture["archetypes"]) == pytest.approx(1)
    assert contrast["lightnessDelta"] > support["lightnessDelta"]
    assert contrast["oklabDistance"] > support["oklabDistance"]


def test_wada_calibration_reduces_membership_diffusion(wada_engine):
    calibrated = wada_engine._cluster_memberships
    uncalibrated = wada_engine._soft_memberships(wada_engine._features, wada_engine._labels)
    effective = lambda memberships: np.exp(-np.sum(np.where(
        memberships > 0, memberships * np.log(memberships), 0,
    ), axis=1)).mean()
    assert effective(calibrated) < effective(uncalibrated) * 0.5


def test_known_color_has_one_exact_anchor(trained_engine):
    color = clustered_dataset().colors[0]
    assert trained_engine._anchor_weights(color) == [(color, 1.0)]


def test_custom_color_uses_normalized_four_neighbor_kernel(trained_engine):
    custom = PaletteColor("custom", "Custom", "#999999", (153, 153, 153))
    anchors = trained_engine._anchor_weights(custom)
    assert len(anchors) == 4
    assert sum(weight for _, weight in anchors) == pytest.approx(1)
    assert all(weight > 0 for _, weight in anchors)


def test_exact_rgb_custom_color_collapses_to_exact_palette_anchor(trained_engine):
    source = clustered_dataset().colors[0]
    custom = PaletteColor("custom", "Custom", source.hex, source.rgb)
    assert trained_engine._anchor_weights(custom) == [(source, 1.0)]


def test_rbf_diversity_kernel_is_symmetric_positive_semidefinite():
    labs = np.asarray([[0.5, 0.1, 0], [0.5, 0.1, 0], [0.8, -0.1, .1]])
    kernel = ClusterEnsembleEngine._rbf_kernel(labs, .1)
    assert kernel == pytest.approx(kernel.T)
    assert np.linalg.eigvalsh(kernel).min() >= -1e-10


def test_recommendations_are_deterministic(trained_engine):
    selected = [clustered_dataset().colors[0]]
    left = [item.color.id for item in trained_engine.recommend(selected, "balanced", 4)]
    right = [item.color.id for item in trained_engine.recommend(selected, "balanced", 4)]
    assert left == right
