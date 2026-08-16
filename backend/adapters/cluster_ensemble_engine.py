from __future__ import annotations

import math
import os
import warnings
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np

if not os.environ.get("LOKY_MAX_CPU_COUNT", "").isdigit():
    os.environ["LOKY_MAX_CPU_COUNT"] = str(os.cpu_count() or 1)
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*", category=UserWarning)

from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, pairwise_distances, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler, normalize

from ..color_space import oklch_to_gamut_mapped_rgb, rgb_to_hex, rgb_to_oklab, rgb_to_oklch
from ..domain import PaletteColor, PaletteDataset, Recommendation


@dataclass
class ClusterEvaluation:
    algorithm: str
    clusters: int
    silhouette: float
    calinski_harabasz: float
    davies_bouldin: float
    group_recall_at_10: float
    group_ndcg_at_10: float
    composite: float = 0.0
    membership_temperature_scale: Optional[float] = None
    soft_group_recall_at_10: Optional[float] = None
    soft_group_ndcg_at_10: Optional[float] = None


@dataclass
class ScoredCandidate:
    recommendation: Recommendation
    lab: tuple[float, float, float]
    base_score: float
    family_scores: tuple[float, ...] = ()
    relation_fit: float = 0.5
    relation_name: str = "general"


class ClusterEnsembleEngine:
    """Selects a clustering model, then builds a perceptually varied palette."""

    id = "cluster-ensemble-v2"
    name = "Wada harmony model"
    _HARMONY_SCHEMES = (
        ("monochromatic", 0.0, 12.0),
        ("analogous", 30.0, 18.0),
        ("tetradic", 90.0, 18.0),
        ("triadic", 120.0, 16.0),
        ("split-complementary", 150.0, 16.0),
        ("complementary", 180.0, 14.0),
    )
    _HARMONY_EMPHASIS = {
        "quiet": {
            "monochromatic": 1.00, "analogous": 1.00, "tetradic": 0.55,
            "triadic": 0.55, "split-complementary": 0.40, "complementary": 0.35,
            "tonal": 1.00,
        },
        "balanced": {
            "monochromatic": 0.70, "analogous": 0.85, "tetradic": 0.90,
            "triadic": 1.00, "split-complementary": 0.95, "complementary": 0.85,
            "tonal": 0.80,
        },
        "vivid": {
            "monochromatic": 0.45, "analogous": 0.55, "tetradic": 0.90,
            "triadic": 0.95, "split-complementary": 1.00, "complementary": 1.00,
            "tonal": 0.65,
        },
    }
    _NEUTRAL_CHROMA = 0.025

    def __init__(self, random_state: int = 42, min_clusters: int = 3, max_clusters: int = 12):
        self._random_state = random_state
        self._min_clusters = min_clusters
        self._max_clusters = max_clusters
        self._dataset: Optional[PaletteDataset] = None
        self._features: Optional[np.ndarray] = None
        self._labels: Optional[np.ndarray] = None
        self._evaluations: list[ClusterEvaluation] = []
        self._selected: Optional[ClusterEvaluation] = None
        self._colors_by_id: dict[str, PaletteColor] = {}
        self._row_by_id: dict[str, int] = {}
        self._oklab_matrix: Optional[np.ndarray] = None
        self._oklch_matrix: Optional[np.ndarray] = None
        self._group_profiles: Optional[np.ndarray] = None
        self._cluster_memberships: Optional[np.ndarray] = None
        self._family_memberships: dict[str, np.ndarray] = {}
        self._family_evaluations: dict[str, ClusterEvaluation] = {}
        self._feature_scale = 1.0
        self._relation_pair_count = 0
        self._relation_centers: Optional[np.ndarray] = None
        self._relation_raw_centers: Optional[np.ndarray] = None
        self._relation_feature_mean: Optional[np.ndarray] = None
        self._relation_feature_scale: Optional[np.ndarray] = None
        self._relation_weights: Optional[np.ndarray] = None

    @staticmethod
    def _weighted_incidence(dataset: PaletteDataset, group_ids: list[str]) -> np.ndarray:
        if not group_ids:
            return np.zeros((len(dataset.colors), 0), dtype=float)
        group_columns = {group_id: index for index, group_id in enumerate(group_ids)}
        incidence = np.zeros((len(dataset.colors), len(group_ids)), dtype=float)
        for row, color in enumerate(dataset.colors):
            for group_id in dataset.groups_by_color.get(color.id, frozenset()):
                column = group_columns.get(group_id)
                if column is not None:
                    incidence[row, column] = 1.0
        inverse_frequency = np.log((1 + len(dataset.colors)) / (1 + incidence.sum(axis=0))) + 1.0
        return normalize(incidence * inverse_frequency, norm="l2", axis=1)

    @staticmethod
    def _perceptual_features(oklab: np.ndarray) -> np.ndarray:
        """Normalize lightness separately and the a/b plane isotropically."""
        values = np.asarray(oklab, dtype=float)
        if values.ndim != 2 or values.shape[1] != 3:
            raise ValueError("OKLab features must have shape (samples, 3)")
        lightness = values[:, :1] - values[:, :1].mean(axis=0)
        lightness_scale = float(np.sqrt(np.mean(lightness ** 2)))
        chromatic = values[:, 1:] - values[:, 1:].mean(axis=0)
        # A shared a/b scale commutes with every rotation around the neutral
        # axis; independent per-axis scaling does not.
        chromatic_scale = float(np.sqrt(np.mean(np.sum(chromatic ** 2, axis=1)) / 2.0))
        return np.hstack((
            lightness / max(lightness_scale, 1e-12),
            chromatic / max(chromatic_scale, 1e-12),
        ))

    def _feature_matrix(self, dataset: PaletteDataset, group_ids: Optional[list[str]] = None) -> np.ndarray:
        perceptual = self._perceptual_features(np.asarray([rgb_to_oklab(color.rgb) for color in dataset.colors], dtype=float))
        available_groups = sorted({group for groups in dataset.groups_by_color.values() for group in groups})
        selected_groups = available_groups if group_ids is None else group_ids
        if len(selected_groups) < 2:
            return perceptual

        incidence = self._weighted_incidence(dataset, selected_groups)
        component_count = min(8, len(dataset.colors) - 1, len(selected_groups) - 1)
        embedding = TruncatedSVD(n_components=component_count, random_state=self._random_state).fit_transform(incidence)
        embedding = StandardScaler().fit_transform(embedding)
        # Normalize blocks, then favor historical structure 2:1. Perceptual goals
        # are applied explicitly again at recommendation time.
        return np.hstack((0.5 * perceptual / math.sqrt(3), embedding / math.sqrt(component_count)))

    def _candidate_labels(self, algorithm: str, clusters: int, features: np.ndarray) -> np.ndarray:
        if algorithm == "kmeans":
            return KMeans(
                n_clusters=clusters, n_init=20, algorithm="elkan", tol=1e-5,
                random_state=self._random_state,
            ).fit_predict(features)
        if algorithm == "agglomerative":
            return AgglomerativeClustering(n_clusters=clusters, linkage="ward").fit_predict(features)
        if algorithm == "gaussian_mixture":
            model = GaussianMixture(
                n_components=clusters, covariance_type="full", n_init=3,
                reg_covar=1e-5, random_state=self._random_state,
            )
            return model.fit_predict(features)
        raise ValueError(f"Unsupported clustering algorithm: {algorithm}")

    @staticmethod
    def _percentile_ranks(values: list[float], lower_is_better: bool = False) -> list[float]:
        """Return outlier-resistant percentile ranks with average ranks for ties."""
        if len(values) <= 1 or all(math.isclose(values[0], value) for value in values[1:]):
            return [0.5] * len(values)
        ranked = []
        denominator = len(values) - 1
        for value in values:
            lower = sum(other < value and not math.isclose(other, value) for other in values)
            tied = sum(math.isclose(other, value) for other in values)
            percentile = (lower + (tied - 1) / 2) / denominator
            ranked.append(1.0 - percentile if lower_is_better else percentile)
        return ranked

    def _ranked_group_retrieval(
        self,
        dataset: PaletteDataset,
        heldout_groups: list[str],
        affinity: np.ndarray,
    ) -> tuple[float, float]:
        if not heldout_groups:
            return 0.0, 0.0
        affinity = affinity.copy()
        np.fill_diagonal(affinity, -np.inf)
        neighbor_count = min(10, len(dataset.colors) - 1)
        ranked_rows = np.argsort(-affinity, axis=1)[:, :neighbor_count]
        recalls: list[float] = []
        ndcgs: list[float] = []
        for group_id in heldout_groups:
            members = [self._row_by_id[color.id] for color in dataset.colors if group_id in dataset.groups_by_color.get(color.id, frozenset())]
            if len(members) < 2:
                continue
            member_set = set(members)
            for query in members:
                relevant = member_set - {query}
                hits = np.asarray([row in relevant for row in ranked_rows[query]], dtype=float)
                recalls.append(float(hits.sum()) / min(len(relevant), neighbor_count))
                dcg = float(sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits)))
                ideal = sum(1 / math.log2(rank + 2) for rank in range(min(len(relevant), neighbor_count)))
                ndcgs.append(dcg / ideal)
        return (float(np.mean(recalls)), float(np.mean(ndcgs))) if recalls else (0.0, 0.0)

    def _group_retrieval(self, dataset: PaletteDataset, heldout_groups: list[str], features: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
        distances = pairwise_distances(features)
        positive_distances = distances[distances > 0]
        scale = float(np.median(positive_distances)) if positive_distances.size else 1.0
        affinity = 0.65 * (labels[:, None] == labels[None, :]) + 0.35 * np.exp(-distances / max(scale, 1e-9))
        return self._ranked_group_retrieval(dataset, heldout_groups, affinity)

    def _soft_group_retrieval(
        self,
        dataset: PaletteDataset,
        heldout_groups: list[str],
        features: np.ndarray,
        memberships: np.ndarray,
    ) -> tuple[float, float]:
        distances = pairwise_distances(features)
        positive_distances = distances[distances > 0]
        scale = float(np.median(positive_distances)) if positive_distances.size else 1.0
        cluster_affinity = np.sqrt(memberships[:, None, :] * memberships[None, :, :]).sum(axis=2)
        affinity = 0.65 * cluster_affinity + 0.35 * np.exp(-distances / max(scale, 1e-9))
        return self._ranked_group_retrieval(dataset, heldout_groups, affinity)

    def _calibrate_membership_temperature(
        self,
        dataset: PaletteDataset,
        heldout_groups: list[str],
        features: np.ndarray,
        labels: np.ndarray,
    ) -> tuple[float, float, float]:
        candidates = (0.0625, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0)
        evaluated = []
        for scale in candidates:
            memberships = self._soft_memberships(features, labels, scale)
            recall, ndcg = self._soft_group_retrieval(dataset, heldout_groups, features, memberships)
            evaluated.append((ndcg, recall, -abs(math.log2(scale)), scale))
        ndcg, recall, _, scale = max(evaluated)
        return float(scale), float(recall), float(ndcg)

    @staticmethod
    def _relation_vector(
        left_lab: np.ndarray,
        left_lch: np.ndarray,
        right_lab: np.ndarray,
        right_lch: np.ndarray,
    ) -> np.ndarray:
        hue_delta = abs(float(left_lch[2] - right_lch[2]))
        hue_delta = min(hue_delta, 360.0 - hue_delta)
        return np.asarray([
            abs(float(left_lch[0] - right_lch[0])),
            hue_delta / 180.0,
            float(left_lch[1] + right_lch[1]) / 2.0,
            abs(float(left_lch[1] - right_lch[1])),
            float(np.linalg.norm(left_lab - right_lab)) / 0.75,
        ])

    def _fit_relation_mixture(self, dataset: PaletteDataset) -> None:
        assert self._oklab_matrix is not None and self._oklch_matrix is not None
        members_by_group: dict[str, list[int]] = defaultdict(list)
        for row, color in enumerate(dataset.colors):
            for group_id in dataset.groups_by_color.get(color.id, frozenset()):
                members_by_group[group_id].append(row)
        pairs: set[tuple[int, int]] = set()
        for members in members_by_group.values():
            for left_index, left in enumerate(members):
                for right in members[left_index + 1:]:
                    pairs.add((min(left, right), max(left, right)))
        self._relation_pair_count = len(pairs)
        if len(pairs) < 2:
            self._relation_centers = None
            self._relation_raw_centers = None
            self._relation_feature_mean = None
            self._relation_feature_scale = None
            self._relation_weights = None
            return

        pair_features = np.asarray([
            self._relation_vector(
                self._oklab_matrix[left], self._oklch_matrix[left],
                self._oklab_matrix[right], self._oklch_matrix[right],
            )
            for left, right in sorted(pairs)
        ])
        scaler = StandardScaler().fit(pair_features)
        standardized = scaler.transform(pair_features)
        if len(np.unique(standardized, axis=0)) < 2:
            self._relation_centers = None
            self._relation_raw_centers = None
            self._relation_feature_mean = None
            self._relation_feature_scale = None
            self._relation_weights = None
            return
        labels = KMeans(
            n_clusters=2, n_init=50, algorithm="elkan", tol=1e-6,
            random_state=self._random_state,
        ).fit_predict(standardized)
        raw_centers = np.asarray([pair_features[labels == cluster].mean(axis=0) for cluster in range(2)])
        centers = scaler.transform(raw_centers)
        weights = np.asarray([(labels == cluster).mean() for cluster in range(2)])
        # The larger perceptual-distance center is the contrast vector. Ordering
        # support first keeps diagnostics and evidence stable across random seeds.
        order = np.argsort(raw_centers[:, 4])
        self._relation_centers = centers[order]
        self._relation_raw_centers = raw_centers[order]
        self._relation_feature_mean = np.asarray(scaler.mean_)
        self._relation_feature_scale = np.asarray(scaler.scale_)
        self._relation_weights = weights[order]

    def _relation_fit(
        self,
        candidate_lab: tuple[float, float, float],
        candidate_lch: tuple[float, float, float],
        selected_labs: np.ndarray,
        selected_lch: np.ndarray,
    ) -> tuple[float, str]:
        if (
            self._relation_centers is None or self._relation_feature_mean is None
            or self._relation_feature_scale is None or self._relation_weights is None
        ):
            return 0.5, "general"
        lab = np.asarray(candidate_lab)
        lch = np.asarray(candidate_lch)
        similarities = []
        for selected_lab, selected_color_lch in zip(selected_labs, selected_lch):
            vector = self._relation_vector(lab, lch, selected_lab, selected_color_lch)
            standardized = (vector - self._relation_feature_mean) / self._relation_feature_scale
            squared = ((self._relation_centers - standardized) ** 2).mean(axis=1)
            similarities.append(np.exp(-0.5 * squared))
        mean_similarity = np.asarray(similarities).mean(axis=0)
        name = ("support", "contrast")[int(np.argmax(mean_similarity))]
        mixture_fit = float(np.dot(self._relation_weights, mean_similarity))
        return max(0.0, min(1.0, mixture_fit)), name

    def fit(self, dataset: PaletteDataset) -> None:
        if len(dataset.colors) < 4:
            raise ValueError("Cluster ensemble requires at least four colors")
        self._dataset = dataset
        self._colors_by_id = {color.id: color for color in dataset.colors}
        self._row_by_id = {color.id: row for row, color in enumerate(dataset.colors)}
        self._oklab_matrix = np.asarray([rgb_to_oklab(color.rgb) for color in dataset.colors], dtype=float)
        self._oklch_matrix = np.asarray([rgb_to_oklch(color.rgb) for color in dataset.colors], dtype=float)
        self._fit_relation_mixture(dataset)
        self._features = self._feature_matrix(dataset)
        all_groups = sorted({group for groups in dataset.groups_by_color.values() for group in groups})
        self._group_profiles = self._weighted_incidence(dataset, all_groups)
        random = np.random.default_rng(self._random_state)
        heldout_count = max(1, round(len(all_groups) * 0.20)) if all_groups else 0
        heldout_groups = sorted(random.choice(all_groups, size=heldout_count, replace=False).tolist()) if heldout_count else []
        heldout_set = set(heldout_groups)
        training_groups = [group for group in all_groups if group not in heldout_set]
        validation_features = self._feature_matrix(dataset, training_groups)
        self._evaluations = []
        labels_by_candidate: dict[tuple[str, int], np.ndarray] = {}
        validation_labels_by_candidate: dict[tuple[str, int], np.ndarray] = {}
        largest_k = min(self._max_clusters, len(dataset.colors) - 1)
        smallest_k = min(self._min_clusters, largest_k)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*", category=UserWarning)
            for clusters in range(smallest_k, largest_k + 1):
                for algorithm in ("kmeans", "agglomerative", "gaussian_mixture"):
                    try:
                        labels = self._candidate_labels(algorithm, clusters, self._features)
                        validation_labels = self._candidate_labels(algorithm, clusters, validation_features)
                        if not 2 <= len(np.unique(labels)) < len(dataset.colors):
                            continue
                        recall, ndcg = self._group_retrieval(dataset, heldout_groups, validation_features, validation_labels)
                        evaluation = ClusterEvaluation(
                            algorithm=algorithm,
                            clusters=clusters,
                            silhouette=float(silhouette_score(self._features, labels)),
                            calinski_harabasz=float(calinski_harabasz_score(self._features, labels)),
                            davies_bouldin=float(davies_bouldin_score(self._features, labels)),
                            group_recall_at_10=recall,
                            group_ndcg_at_10=ndcg,
                        )
                        self._evaluations.append(evaluation)
                        labels_by_candidate[(algorithm, clusters)] = labels
                        validation_labels_by_candidate[(algorithm, clusters)] = validation_labels
                    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                        continue

        if not self._evaluations:
            raise ValueError("No valid clustering candidate could be trained")
        silhouettes = self._percentile_ranks([item.silhouette for item in self._evaluations])
        calinski = self._percentile_ranks([item.calinski_harabasz for item in self._evaluations])
        davies = self._percentile_ranks([item.davies_bouldin for item in self._evaluations], lower_is_better=True)
        retrieval = self._percentile_ranks([item.group_recall_at_10 for item in self._evaluations])
        ndcg = self._percentile_ranks([item.group_ndcg_at_10 for item in self._evaluations])
        cluster_span = max(1, largest_k - smallest_k)
        for index, evaluation in enumerate(self._evaluations):
            parsimony = 1 - (evaluation.clusters - smallest_k) / cluster_span
            evaluation.composite = (
                0.20 * silhouettes[index] + 0.10 * calinski[index] + 0.10 * davies[index]
                + 0.30 * retrieval[index] + 0.25 * ndcg[index] + 0.05 * parsimony
            )
        self._selected = max(
            self._evaluations,
            key=lambda item: (item.composite, item.group_ndcg_at_10, item.group_recall_at_10, item.silhouette),
        )
        self._labels = labels_by_candidate[(self._selected.algorithm, self._selected.clusters)]
        self._family_evaluations = {}
        for evaluation in self._evaluations:
            current = self._family_evaluations.get(evaluation.algorithm)
            if current is None or (
                evaluation.composite, evaluation.group_ndcg_at_10,
                evaluation.group_recall_at_10, evaluation.silhouette,
            ) > (
                current.composite, current.group_ndcg_at_10,
                current.group_recall_at_10, current.silhouette,
            ):
                self._family_evaluations[evaluation.algorithm] = evaluation
        self._family_memberships = {}
        for algorithm, evaluation in self._family_evaluations.items():
            key = (algorithm, evaluation.clusters)
            scale, recall, ndcg = self._calibrate_membership_temperature(
                dataset, heldout_groups, validation_features, validation_labels_by_candidate[key],
            )
            evaluation.membership_temperature_scale = scale
            evaluation.soft_group_recall_at_10 = recall
            evaluation.soft_group_ndcg_at_10 = ndcg
            self._family_memberships[algorithm] = self._soft_memberships(
                self._features, labels_by_candidate[key], scale,
            )
        self._cluster_memberships = self._family_memberships[self._selected.algorithm]
        feature_distances = pairwise_distances(self._features)
        positive_distances = feature_distances[feature_distances > 0]
        self._feature_scale = float(np.median(positive_distances)) if positive_distances.size else 1.0

    @staticmethod
    def _soft_memberships(features: np.ndarray, labels: np.ndarray, temperature_scale: float = 1.0) -> np.ndarray:
        """Turn hard cluster assignments into smooth probability vectors."""
        if temperature_scale <= 0:
            raise ValueError("Membership temperature scale must be positive")
        cluster_ids = sorted(int(label) for label in np.unique(labels))
        centroids = np.asarray([features[labels == cluster_id].mean(axis=0) for cluster_id in cluster_ids])
        squared = ((features[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        assigned = np.asarray([squared[row, cluster_ids.index(int(label))] for row, label in enumerate(labels)])
        positive = assigned[assigned > 1e-12]
        temperature = float(np.median(positive)) if positive.size else float(np.median(squared[squared > 0]))
        logits = -squared / max(2 * temperature * temperature_scale, 1e-9)
        logits -= logits.max(axis=1, keepdims=True)
        probabilities = np.exp(logits)
        return probabilities / probabilities.sum(axis=1, keepdims=True)

    def _anchor_weights(self, color: PaletteColor, count: int = 4) -> list[tuple[PaletteColor, float]]:
        known = self._colors_by_id.get(color.id)
        if known is not None:
            return [(known, 1.0)]
        assert self._dataset is not None and self._oklab_matrix is not None
        target = np.asarray(rgb_to_oklab(color.rgb))
        distances = np.linalg.norm(self._oklab_matrix - target, axis=1)
        neighbor_count = min(count, len(self._dataset.colors))
        indices = np.argsort(distances)[:neighbor_count]
        if distances[indices[0]] < 1e-12:
            return [(self._dataset.colors[int(indices[0])], 1.0)]
        bandwidth = max(float(np.median(distances[indices])), 0.015)
        raw = np.exp(-0.5 * (distances[indices] / bandwidth) ** 2)
        weights = raw / raw.sum()
        return [(self._dataset.colors[int(index)], float(weight)) for index, weight in zip(indices, weights)]

    @staticmethod
    def _mixture(matrix: np.ndarray, weighted_rows: list[tuple[int, float]]) -> np.ndarray:
        return sum((weight * matrix[row] for row, weight in weighted_rows), start=np.zeros(matrix.shape[1], dtype=float))

    @staticmethod
    def _unit(vector: np.ndarray) -> np.ndarray:
        magnitude = float(np.linalg.norm(vector))
        return vector / magnitude if magnitude > 1e-12 else vector

    @staticmethod
    def _hue_name(hue: float) -> str:
        names = ("Crimson", "Vermilion", "Amber", "Yellow", "Chartreuse", "Green", "Viridian", "Cyan", "Azure", "Blue", "Violet", "Magenta")
        return names[round(hue / 30) % len(names)]

    def _spectrum_candidates(self, selected_colors: list[PaletteColor], mode: str) -> list[PaletteColor]:
        lch_values = [rgb_to_oklch(color.rgb) for color in selected_colors]
        lightness = sum(value[0] for value in lch_values) / len(lch_values)
        chroma = sum(value[1] for value in lch_values) / len(lch_values)
        hue_weights = [max(value[1], 0.01) for value in lch_values]
        x = sum(weight * math.cos(math.radians(value[2])) for value, weight in zip(lch_values, hue_weights))
        y = sum(weight * math.sin(math.radians(value[2])) for value, weight in zip(lch_values, hue_weights))
        concentration = math.hypot(x, y) / sum(hue_weights)
        hue_centers = [math.degrees(math.atan2(y, x)) % 360] if concentration >= 0.15 else list(dict.fromkeys(round(value[2], 6) for value in lch_values))
        if mode == "quiet":
            offsets, lightness_steps, target_chroma = (-45, -28, -14, 0, 14, 28, 45), (-0.10, 0, 0.10), min(0.13, max(0.035, chroma * 0.72))
        elif mode == "vivid":
            offsets, lightness_steps, target_chroma = (-150, -120, -90, -60, 60, 90, 120, 150, 180), (-0.24, -0.08, 0.10, 0.22), min(0.29, max(0.18, chroma * 1.18))
        else:
            offsets, lightness_steps, target_chroma = (-120, -60, -30, 30, 60, 120, 180), (-0.16, -0.05, 0.08, 0.17), min(0.21, max(0.09, chroma * 0.95))

        candidates: dict[str, PaletteColor] = {}
        selected_labs = np.asarray([rgb_to_oklab(color.rgb) for color in selected_colors])
        for hue in hue_centers:
            for offset in offsets:
                candidate_hue = (hue + offset) % 360
                for step in lightness_steps:
                    candidate_lightness = max(0.20, min(0.88, lightness + step))
                    rgb = oklch_to_gamut_mapped_rgb(candidate_lightness, target_chroma, candidate_hue)
                    candidate_lab = np.asarray(rgb_to_oklab(rgb))
                    if float(np.linalg.norm(selected_labs - candidate_lab, axis=1).min()) / 0.75 < 0.07:
                        continue
                    hex_value = rgb_to_hex(rgb)
                    realized_lightness, _, realized_hue = rgb_to_oklch(rgb)
                    tone = "Pale " if realized_lightness > 0.76 else "Deep " if realized_lightness < 0.38 else ""
                    candidates[hex_value] = PaletteColor(
                        f"generated:{hex_value}", f"Spectrum {tone}{self._hue_name(realized_hue)}", hex_value, rgb,
                        {"generated": True, "source": "spectrum", "gamutMapped": True},
                    )
        return list(candidates.values())

    @staticmethod
    def _relationship(hue_delta: float) -> str:
        if hue_delta < 25:
            return "analogous hue"
        if hue_delta > 155:
            return "complementary hue"
        if 105 <= hue_delta <= 135:
            return "triadic interval"
        if 55 <= hue_delta <= 95:
            return "wide hue interval"
        return "supporting hue interval"

    def _mood_score(
        self,
        candidate_lch: tuple[float, float, float],
        selected_lch: np.ndarray,
        mode: str,
    ) -> tuple[float, str]:
        candidate_l, candidate_c, candidate_h = candidate_lch
        hue_delta = float(np.minimum(
            np.abs(selected_lch[:, 2] - candidate_h),
            360 - np.abs(selected_lch[:, 2] - candidate_h),
        ).mean())
        hue_factor = hue_delta / 180.0
        lightness_delta = float(np.abs(selected_lch[:, 0] - candidate_l).mean())
        chroma_factor = min(1.0, candidate_c / 0.30)
        if mode == "quiet":
            score = 0.45 * (1 - hue_factor) + 0.30 * (1 - chroma_factor) + 0.25 * (1 - lightness_delta)
        elif mode == "vivid":
            score = 0.45 * chroma_factor + 0.35 * hue_factor + 0.20 * min(1.0, lightness_delta / 0.55)
        else:
            hue_balance = max(0.0, 1 - abs(hue_factor - 0.55) / 0.55)
            chroma_balance = max(0.0, 1 - abs(chroma_factor - 0.58) / 0.58)
            value_balance = max(0.0, 1 - abs(lightness_delta - 0.28) / 0.72)
            score = 0.40 * hue_balance + 0.30 * chroma_balance + 0.30 * value_balance
        return max(0.0, min(1.0, score)), f"{self._relationship(hue_delta)} · {round(hue_delta)}° · ΔL {round(lightness_delta * 100)}"

    def _harmony_fit(
        self,
        candidate_lch: tuple[float, float, float],
        selected_lch: np.ndarray,
        mode: str,
    ) -> tuple[float, str, str]:
        """Score classical color-wheel relationships independently of history."""
        candidate_l, candidate_c, candidate_h = candidate_lch
        emphasis = self._HARMONY_EMPHASIS[mode]
        pair_scores: list[float] = []
        scheme_totals: dict[str, float] = defaultdict(float)
        scheme_hue_deltas: dict[str, list[float]] = defaultdict(list)
        lightness_deltas: list[float] = []
        for selected_color_lch in selected_lch:
            selected_l, selected_c, selected_h = selected_color_lch
            lightness_delta = abs(float(selected_l - candidate_l))
            lightness_deltas.append(lightness_delta)
            if min(float(selected_c), candidate_c) < self._NEUTRAL_CHROMA:
                tonal_shape = math.exp(-0.5 * ((lightness_delta - 0.28) / 0.22) ** 2)
                tonal_score = emphasis["tonal"] * (0.65 + 0.35 * tonal_shape)
                pair_scores.append(tonal_score)
                scheme_totals["tonal"] += tonal_score
                continue

            hue_delta = abs(float(selected_h - candidate_h))
            hue_delta = min(hue_delta, 360.0 - hue_delta)
            scored_schemes = [
                (
                    emphasis[name] * math.exp(-0.5 * ((hue_delta - target) / tolerance) ** 2),
                    name,
                )
                for name, target, tolerance in self._HARMONY_SCHEMES
            ]
            score, name = max(scored_schemes)
            pair_scores.append(score)
            scheme_totals[name] += score
            scheme_hue_deltas[name].append(hue_delta)

        harmony_score = float(np.mean(pair_scores)) if pair_scores else 0.0
        harmony_name = max(scheme_totals, key=scheme_totals.get) if scheme_totals else "tonal"
        lightness_delta = float(np.mean(lightness_deltas)) if lightness_deltas else 0.0
        label = harmony_name.replace("-", " ")
        if scheme_hue_deltas.get(harmony_name) and harmony_name != "tonal":
            hue_delta = float(np.mean(scheme_hue_deltas[harmony_name]))
            detail = f"{round(harmony_score * 100)}% classical harmony fit · {label} at {round(hue_delta)}° · ΔL {round(lightness_delta * 100)}"
        else:
            detail = f"{round(harmony_score * 100)}% tonal harmony fit · ΔL {round(lightness_delta * 100)}"
        return max(0.0, min(1.0, harmony_score)), harmony_name, detail

    def _score_candidate(
        self,
        candidate: PaletteColor,
        selected_labs: np.ndarray,
        selected_lch: np.ndarray,
        selected_feature_profile: np.ndarray,
        selected_cluster_profiles: dict[str, np.ndarray],
        selected_group_profile: np.ndarray,
        observed_groups: frozenset[str],
        custom_anchor_names: tuple[str, ...],
        mode: str,
        scope: str,
    ) -> Optional[ScoredCandidate]:
        assert self._dataset is not None and self._features is not None and self._oklab_matrix is not None and self._oklch_matrix is not None
        assert self._selected is not None and self._cluster_memberships is not None and self._group_profiles is not None
        known_row = self._row_by_id.get(candidate.id)
        if known_row is not None:
            candidate_groups = self._dataset.groups_by_color.get(candidate.id, frozenset())
            candidate_cluster_profiles = {
                algorithm: memberships[known_row]
                for algorithm, memberships in self._family_memberships.items()
            }
            candidate_group_profile = self._group_profiles[known_row]
            candidate_feature_profile = self._features[known_row]
            candidate_lch = tuple(self._oklch_matrix[known_row])
            candidate_lab = tuple(self._oklab_matrix[known_row])
        else:
            candidate_anchors = self._anchor_weights(candidate)
            candidate_rows = [(self._row_by_id[anchor.id], weight) for anchor, weight in candidate_anchors]
            candidate_groups = frozenset().union(*(self._dataset.groups_by_color.get(anchor.id, frozenset()) for anchor, _ in candidate_anchors))
            candidate_cluster_profiles = {
                algorithm: self._mixture(memberships, candidate_rows)
                for algorithm, memberships in self._family_memberships.items()
            }
            candidate_group_profile = self._unit(self._mixture(self._group_profiles, candidate_rows))
            candidate_feature_profile = self._mixture(self._features, candidate_rows)
            candidate_lch = rgb_to_oklch(candidate.rgb)
            candidate_lab = rgb_to_oklab(candidate.rgb)
        shared = len(candidate_groups & observed_groups)
        cluster_affinities = {
            algorithm: float(np.sqrt(profile * selected_cluster_profiles[algorithm]).sum())
            for algorithm, profile in candidate_cluster_profiles.items()
        }
        cluster_affinity = cluster_affinities[self._selected.algorithm]
        group_affinity = float(np.dot(candidate_group_profile, selected_group_profile))
        if scope == "palette" and shared == 0 and group_affinity < 0.05 and cluster_affinity < 0.25:
            return None
        distance = float(np.linalg.norm(candidate_feature_profile - selected_feature_profile))
        proximity = math.exp(-0.5 * (distance / max(self._feature_scale, 1e-9)) ** 2)
        mood, _ = self._mood_score(candidate_lch, selected_lch, mode)
        harmony, _, harmony_detail = self._harmony_fit(candidate_lch, selected_lch, mode)
        relation_fit, relation_name = self._relation_fit(
            candidate_lab, candidate_lch, selected_labs, selected_lch,
        )
        weights = self._score_weights(scope)
        family_scores = tuple(
            weights["group"] * group_affinity
            + weights["cluster"] * cluster_affinities[algorithm]
            + weights["proximity"] * proximity
            + weights["mood"] * mood
            + weights["relation"] * relation_fit
            + weights["harmony"] * harmony
            for algorithm in self._family_memberships
        )
        primary_index = tuple(self._family_memberships).index(self._selected.algorithm)
        score = family_scores[primary_index]
        details = [harmony_detail]
        if custom_anchor_names:
            details.append(f"Input interpreted through {', '.join(custom_anchor_names)}")
        if shared:
            details.append(f"Appears through {shared} related Wada {'combination' if shared == 1 else 'combinations'}")
        if candidate.metadata.get("generated"):
            details.append("Generated in perceptual OKLCH space")
        label = ("shared Wada group" if shared == 1 else "shared Wada groups") if shared else "model affinity"
        value = shared if shared else round(max(group_affinity, cluster_affinity) * 100)
        recommendation = Recommendation(candidate, max(0.0, min(1.0, score)), label, value, tuple(details))
        return ScoredCandidate(recommendation, candidate_lab, score, family_scores, relation_fit, relation_name)

    @staticmethod
    def _score_weights(scope: str) -> dict[str, float]:
        if scope == "spectrum":
            return {
                "group": 0.18, "cluster": 0.10, "proximity": 0.10,
                "mood": 0.28, "relation": 0.10, "harmony": 0.24,
            }
        return {
            "group": 0.34, "cluster": 0.14, "proximity": 0.11,
            "mood": 0.13, "relation": 0.10, "harmony": 0.18,
        }

    def _attach_consensus_confidence(self, candidates: list[ScoredCandidate]) -> None:
        if not candidates:
            return
        family_count = len(candidates[0].family_scores)
        family_percentiles = np.asarray([
            self._percentile_ranks([candidate.family_scores[family] for candidate in candidates])
            for family in range(family_count)
        ])
        maximum_std = math.sqrt(family_count - 1) / family_count if family_count > 1 else 1.0
        for index, candidate in enumerate(candidates):
            if family_count > 1:
                confidence = 1.0 - float(np.std(family_percentiles[:, index])) / maximum_std
                confidence = max(0.0, min(1.0, confidence))
                fit_detail = (
                    f"{round(confidence * 100)}% model rank agreement · "
                    f"{round(candidate.relation_fit * 100)}% historic {candidate.relation_name} fit"
                )
            else:
                fit_detail = f"{round(candidate.relation_fit * 100)}% historic {candidate.relation_name} fit"
            recommendation = candidate.recommendation
            details = (recommendation.evidence_details[0], fit_detail, *recommendation.evidence_details[1:])
            candidate.recommendation = Recommendation(
                recommendation.color, recommendation.score, recommendation.evidence_label,
                recommendation.evidence_value, details,
            )

    @staticmethod
    def _rbf_kernel(labs: np.ndarray, bandwidth: float) -> np.ndarray:
        squared = ((labs[:, None, :] - labs[None, :, :]) ** 2).sum(axis=2)
        return np.exp(-squared / max(2 * bandwidth ** 2, 1e-12))

    def _rerank(self, candidates: list[ScoredCandidate], mode: str, limit: int) -> list[Recommendation]:
        if not candidates or limit <= 0:
            return []
        remaining = list(range(len(candidates)))
        chosen: list[int] = []
        diversity_weight = {"quiet": 0.025, "balanced": 0.065, "vivid": 0.10}[mode]
        bandwidth = {"quiet": 0.07, "balanced": 0.10, "vivid": 0.13}[mode]
        kernel = self._rbf_kernel(np.asarray([item.lab for item in candidates]), bandwidth)
        quality = np.asarray([item.base_score for item in candidates])
        while remaining and len(chosen) < limit:
            if not chosen:
                marginal = quality[remaining]
            else:
                chosen_kernel = kernel[np.ix_(chosen, chosen)] + np.eye(len(chosen)) * 1e-6
                cross_kernel = kernel[np.ix_(chosen, remaining)]
                projection = np.linalg.solve(chosen_kernel, cross_kernel)
                conditional_variance = 1.0 + 1e-6 - np.sum(cross_kernel * projection, axis=0)
                logdet_gain = np.log(np.maximum(conditional_variance, 1e-12)).clip(-1.0, 0.0)
                marginal = quality[remaining] + diversity_weight * logdet_gain
            selected_position = int(np.argmax(marginal))
            chosen.append(remaining.pop(selected_position))
        return [candidates[index].recommendation for index in chosen]

    def recommend(self, selected_colors: list[PaletteColor], mode: str = "balanced", limit: int = 4, scope: str = "palette") -> list[Recommendation]:
        if (
            self._dataset is None or self._features is None or self._labels is None
            or self._cluster_memberships is None or self._group_profiles is None
        ):
            raise RuntimeError("Engine must be fit before inference")
        if not selected_colors or limit <= 0:
            return []
        if mode not in {"quiet", "balanced", "vivid"}:
            raise ValueError(f"Unknown harmony mode: {mode}")
        if scope not in {"palette", "spectrum"}:
            raise ValueError(f"Unknown recommendation scope: {scope}")

        selected_anchor_rows: list[tuple[int, float]] = []
        observed_groups: set[str] = set()
        custom_anchor_names: list[str] = []
        excluded = {color.id for color in selected_colors}
        for selected in selected_colors:
            anchors = self._anchor_weights(selected)
            if selected.id not in self._colors_by_id:
                custom_anchor_names.extend(anchor.name for anchor, _ in anchors)
            for anchor, weight in anchors:
                row = self._row_by_id[anchor.id]
                selected_anchor_rows.append((row, weight / len(selected_colors)))
                observed_groups.update(self._dataset.groups_by_color.get(anchor.id, frozenset()))
                excluded.add(anchor.id)

        selected_feature_profile = self._mixture(self._features, selected_anchor_rows)
        selected_cluster_profiles = {
            algorithm: self._mixture(memberships, selected_anchor_rows)
            for algorithm, memberships in self._family_memberships.items()
        }
        selected_group_profile = self._unit(self._mixture(self._group_profiles, selected_anchor_rows))
        selected_labs = np.asarray([rgb_to_oklab(color.rgb) for color in selected_colors])
        selected_lch = np.asarray([rgb_to_oklch(color.rgb) for color in selected_colors])

        pool = self._dataset.colors if scope == "palette" else tuple(self._spectrum_candidates(selected_colors, mode))
        scored = [
            scored_candidate
            for candidate in pool
            if candidate.id not in excluded
            for scored_candidate in [self._score_candidate(
                candidate, selected_labs, selected_lch, selected_feature_profile, selected_cluster_profiles,
                selected_group_profile, frozenset(observed_groups),
                tuple(dict.fromkeys(custom_anchor_names)), mode, scope,
            )]
            if scored_candidate is not None
        ]
        self._attach_consensus_confidence(scored)
        return self._rerank(scored, mode, limit)

    def diagnostics(self) -> dict:
        if self._dataset is None or self._features is None or self._selected is None:
            raise RuntimeError("Engine must be fit before diagnostics")
        leaderboard = sorted(self._evaluations, key=lambda item: item.composite, reverse=True)
        return {
            "engine": {"id": self.id, "name": self.name},
            "training": {
                "samples": len(self._dataset.colors),
                "groups": self._dataset.group_count,
                "features": int(self._features.shape[1]),
                "randomState": self._random_state,
                "colorSpace": "OKLab / OKLCH",
                "featureDesign": "rotation-equivariant OKLab + L2-normalized TF-IDF group SVD",
                "anchorProjection": "adaptive four-neighbor Gaussian kernel",
                "paletteSelection": "greedy determinantal diversity",
                "validation": "seeded 20% group holdout",
                "membershipCalibration": "held-out NDCG@10 temperature search",
                "relationModel": "two-component historical pair mixture",
                "harmonyModel": "mode-weighted classical OKLCH hue intervals",
            },
            "selected": asdict(self._selected),
            "candidates": [asdict(item) for item in leaderboard],
            "ensemble": {
                "primary": {"algorithm": self._selected.algorithm, "clusters": self._selected.clusters},
                "members": [
                    {
                        "algorithm": evaluation.algorithm,
                        "clusters": evaluation.clusters,
                        "composite": evaluation.composite,
                        "membershipTemperatureScale": evaluation.membership_temperature_scale,
                        "softGroupRecallAt10": evaluation.soft_group_recall_at_10,
                        "softGroupNdcgAt10": evaluation.soft_group_ndcg_at_10,
                    }
                    for evaluation in self._family_evaluations.values()
                ],
                "confidence": "candidate rank-percentile agreement across model families",
            },
            "relationMixture": {
                "pairCount": self._relation_pair_count,
                "archetypes": [] if self._relation_raw_centers is None or self._relation_weights is None else [
                    {
                        "name": name,
                        "weight": float(self._relation_weights[index]),
                        "lightnessDelta": float(center[0]),
                        "hueDegrees": float(center[1] * 180.0),
                        "meanChroma": float(center[2]),
                        "chromaDelta": float(center[3]),
                        "oklabDistance": float(center[4]),
                    }
                    for index, (name, center) in enumerate(zip(("support", "contrast"), self._relation_raw_centers))
                ],
            },
            "harmonyModel": {
                "colorSpace": "OKLCH",
                "neutralChromaThreshold": self._NEUTRAL_CHROMA,
                "schemes": [
                    {"name": name, "targetDegrees": target, "toleranceDegrees": tolerance}
                    for name, target, tolerance in self._HARMONY_SCHEMES
                ],
                "modeEmphasis": self._HARMONY_EMPHASIS,
            },
            "scoreWeights": {
                "palette": self._score_weights("palette"),
                "spectrum": self._score_weights("spectrum"),
            },
            "metricWeights": {
                "silhouette": 0.20,
                "calinskiHarabasz": 0.10,
                "daviesBouldin": 0.10,
                "groupRecallAt10": 0.30,
                "groupNdcgAt10": 0.25,
                "parsimony": 0.05,
            },
        }
