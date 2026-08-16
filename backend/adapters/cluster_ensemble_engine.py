from __future__ import annotations

import math
import os
import warnings
from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np

if not os.environ.get("LOKY_MAX_CPU_COUNT", "").isdigit():
    os.environ["LOKY_MAX_CPU_COUNT"] = str(os.cpu_count() or 1)
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*", category=UserWarning)

from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from ..color_space import hue_distance, oklch_to_rgb, perceptual_distance, rgb_to_hex, rgb_to_oklab, rgb_to_oklch
from ..domain import PaletteColor, PaletteDataset, Recommendation


@dataclass
class ClusterEvaluation:
    algorithm: str
    clusters: int
    silhouette: float
    calinski_harabasz: float
    davies_bouldin: float
    group_recall_at_10: float
    composite: float = 0.0


@dataclass
class ScoredCandidate:
    recommendation: Recommendation
    lch: tuple[float, float, float]
    base_score: float


class ClusterEnsembleEngine:
    """Selects a clustering model, then builds a perceptually varied palette."""

    id = "cluster-ensemble-v1"
    name = "Wada harmony model"

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

    @staticmethod
    def _distance(left: PaletteColor, right: PaletteColor) -> float:
        return perceptual_distance(left.rgb, right.rgb)

    def _feature_matrix(self, dataset: PaletteDataset, group_ids: Optional[list[str]] = None) -> np.ndarray:
        perceptual = np.asarray([rgb_to_oklab(color.rgb) for color in dataset.colors], dtype=float)
        available_groups = sorted({group for groups in dataset.groups_by_color.values() for group in groups})
        selected_groups = available_groups if group_ids is None else group_ids
        if len(selected_groups) < 2:
            return StandardScaler().fit_transform(perceptual)

        group_columns = {group_id: index for index, group_id in enumerate(selected_groups)}
        incidence = np.zeros((len(dataset.colors), len(selected_groups)), dtype=float)
        for row, color in enumerate(dataset.colors):
            for group_id in dataset.groups_by_color.get(color.id, frozenset()):
                column = group_columns.get(group_id)
                if column is not None:
                    incidence[row, column] = 1.0

        component_count = min(12, len(dataset.colors) - 1, len(selected_groups) - 1)
        embedding = TruncatedSVD(n_components=component_count, random_state=self._random_state).fit_transform(incidence)
        return StandardScaler().fit_transform(np.hstack((perceptual, embedding)))

    def _candidate_labels(self, algorithm: str, clusters: int, features: np.ndarray) -> np.ndarray:
        if algorithm == "kmeans":
            return KMeans(n_clusters=clusters, n_init=20, random_state=self._random_state).fit_predict(features)
        if algorithm == "agglomerative":
            return AgglomerativeClustering(n_clusters=clusters, linkage="ward").fit_predict(features)
        if algorithm == "gaussian_mixture":
            model = GaussianMixture(n_components=clusters, covariance_type="diag", n_init=3, random_state=self._random_state)
            return model.fit_predict(features)
        raise ValueError(f"Unsupported clustering algorithm: {algorithm}")

    @staticmethod
    def _normalized(values: list[float], lower_is_better: bool = False) -> list[float]:
        low, high = min(values), max(values)
        if math.isclose(low, high):
            return [0.5] * len(values)
        scaled = [(value - low) / (high - low) for value in values]
        return [1.0 - value for value in scaled] if lower_is_better else scaled

    def _group_recall(self, dataset: PaletteDataset, heldout_groups: list[str], features: np.ndarray, labels: np.ndarray) -> float:
        if not heldout_groups:
            return 0.0
        scale = max(math.sqrt(features.shape[1]), 1.0)
        recalls: list[float] = []
        for group_id in heldout_groups:
            members = [self._row_by_id[color.id] for color in dataset.colors if group_id in dataset.groups_by_color.get(color.id, frozenset())]
            if len(members) < 2:
                continue
            member_set = set(members)
            for query in members:
                ranked = sorted(
                    (row for row in range(len(dataset.colors)) if row != query),
                    key=lambda row: (
                        0.72 * float(labels[row] == labels[query])
                        + 0.28 * math.exp(-float(np.linalg.norm(features[row] - features[query])) / scale)
                    ),
                    reverse=True,
                )[:10]
                relevant = member_set - {query}
                recalls.append(len(relevant & set(ranked)) / min(len(relevant), 10))
        return float(np.mean(recalls)) if recalls else 0.0

    def fit(self, dataset: PaletteDataset) -> None:
        if len(dataset.colors) < 4:
            raise ValueError("Cluster ensemble requires at least four colors")
        self._dataset = dataset
        self._colors_by_id = {color.id: color for color in dataset.colors}
        self._row_by_id = {color.id: row for row, color in enumerate(dataset.colors)}
        self._features = self._feature_matrix(dataset)
        all_groups = sorted({group for groups in dataset.groups_by_color.values() for group in groups})
        heldout_groups = all_groups[::5]
        training_groups = [group for group in all_groups if group not in set(heldout_groups)]
        validation_features = self._feature_matrix(dataset, training_groups)
        self._evaluations = []
        labels_by_candidate: dict[tuple[str, int], np.ndarray] = {}
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
                        evaluation = ClusterEvaluation(
                            algorithm=algorithm,
                            clusters=clusters,
                            silhouette=float(silhouette_score(self._features, labels)),
                            calinski_harabasz=float(calinski_harabasz_score(self._features, labels)),
                            davies_bouldin=float(davies_bouldin_score(self._features, labels)),
                            group_recall_at_10=self._group_recall(dataset, heldout_groups, validation_features, validation_labels),
                        )
                        self._evaluations.append(evaluation)
                        labels_by_candidate[(algorithm, clusters)] = labels
                    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                        continue

        if not self._evaluations:
            raise ValueError("No valid clustering candidate could be trained")
        silhouettes = self._normalized([item.silhouette for item in self._evaluations])
        calinski = self._normalized([item.calinski_harabasz for item in self._evaluations])
        davies = self._normalized([item.davies_bouldin for item in self._evaluations], lower_is_better=True)
        retrieval = self._normalized([item.group_recall_at_10 for item in self._evaluations])
        for index, evaluation in enumerate(self._evaluations):
            evaluation.composite = 0.30 * silhouettes[index] + 0.15 * calinski[index] + 0.15 * davies[index] + 0.40 * retrieval[index]
        self._selected = max(self._evaluations, key=lambda item: (item.composite, item.group_recall_at_10, item.silhouette))
        self._labels = labels_by_candidate[(self._selected.algorithm, self._selected.clusters)]

    def _anchor_weights(self, color: PaletteColor, count: int = 3) -> list[tuple[PaletteColor, float]]:
        known = self._colors_by_id.get(color.id)
        if known is not None:
            return [(known, 1.0)]
        assert self._dataset is not None
        neighbors = sorted(self._dataset.colors, key=lambda candidate: self._distance(color, candidate))[:count]
        raw = [1.0 / (self._distance(color, candidate) + 0.02) ** 2 for candidate in neighbors]
        total = sum(raw)
        return [(candidate, weight / total) for candidate, weight in zip(neighbors, raw)]

    @staticmethod
    def _hue_name(hue: float) -> str:
        names = ("Crimson", "Vermilion", "Amber", "Yellow", "Chartreuse", "Green", "Viridian", "Cyan", "Azure", "Blue", "Violet", "Magenta")
        return names[round(hue / 30) % len(names)]

    def _spectrum_candidates(self, selected_colors: list[PaletteColor], mode: str) -> list[PaletteColor]:
        lch_values = [rgb_to_oklch(color.rgb) for color in selected_colors]
        lightness = sum(value[0] for value in lch_values) / len(lch_values)
        chroma = sum(value[1] for value in lch_values) / len(lch_values)
        x = sum(math.cos(math.radians(value[2])) for value in lch_values)
        y = sum(math.sin(math.radians(value[2])) for value in lch_values)
        hue = math.degrees(math.atan2(y, x)) % 360
        if mode == "quiet":
            offsets, lightness_steps, target_chroma = (-45, -28, -14, 0, 14, 28, 45), (-0.10, 0, 0.10), min(0.13, max(0.035, chroma * 0.72))
        elif mode == "vivid":
            offsets, lightness_steps, target_chroma = (-150, -120, -90, -60, 60, 90, 120, 150, 180), (-0.24, -0.08, 0.10, 0.22), min(0.29, max(0.18, chroma * 1.18))
        else:
            offsets, lightness_steps, target_chroma = (-120, -60, -30, 30, 60, 120, 180), (-0.16, -0.05, 0.08, 0.17), min(0.21, max(0.09, chroma * 0.95))

        candidates: dict[str, PaletteColor] = {}
        for offset in offsets:
            candidate_hue = (hue + offset) % 360
            for step in lightness_steps:
                candidate_lightness = max(0.20, min(0.88, lightness + step))
                rgb = oklch_to_rgb(candidate_lightness, target_chroma, candidate_hue)
                if min(self._distance(PaletteColor("", "", "", rgb), selected) for selected in selected_colors) < 0.07:
                    continue
                hex_value = rgb_to_hex(rgb)
                realized_lightness, _, realized_hue = rgb_to_oklch(rgb)
                tone = "Pale " if realized_lightness > 0.76 else "Deep " if realized_lightness < 0.38 else ""
                candidates[hex_value] = PaletteColor(
                    f"generated:{hex_value}", f"Spectrum {tone}{self._hue_name(realized_hue)}", hex_value, rgb,
                    {"generated": True, "source": "spectrum"},
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

    def _mood_score(self, candidate: PaletteColor, selected_colors: list[PaletteColor], mode: str) -> tuple[float, str]:
        candidate_l, candidate_c, candidate_h = rgb_to_oklch(candidate.rgb)
        selected_lch = [rgb_to_oklch(color.rgb) for color in selected_colors]
        hue_delta = sum(hue_distance(candidate_h, value[2]) for value in selected_lch) / len(selected_lch)
        hue_factor = hue_delta / 180.0
        lightness_delta = sum(abs(candidate_l - value[0]) for value in selected_lch) / len(selected_lch)
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

    def _score_candidate(
        self,
        candidate: PaletteColor,
        selected_colors: list[PaletteColor],
        selected_anchor_rows: list[tuple[int, float]],
        selected_labels: set[int],
        observed_groups: frozenset[str],
        custom_anchor_names: tuple[str, ...],
        mode: str,
        scope: str,
    ) -> Optional[ScoredCandidate]:
        assert self._dataset is not None and self._features is not None and self._labels is not None
        candidate_anchors = self._anchor_weights(candidate)
        candidate_rows = [(self._row_by_id[anchor.id], weight) for anchor, weight in candidate_anchors]
        candidate_groups = frozenset().union(*(self._dataset.groups_by_color.get(anchor.id, frozenset()) for anchor, _ in candidate_anchors))
        shared = len(candidate_groups & observed_groups)
        cluster_affinity = sum(weight for row, weight in candidate_rows if int(self._labels[row]) in selected_labels)
        if scope == "palette" and cluster_affinity <= 0 and shared == 0:
            return None
        co_occurrence = shared / math.sqrt(max(1, len(candidate_groups) * len(observed_groups)))
        feature_scale = max(math.sqrt(self._features.shape[1]), 1.0)
        distance = sum(
            candidate_weight * selected_weight * float(np.linalg.norm(self._features[candidate_row] - self._features[selected_row]))
            for candidate_row, candidate_weight in candidate_rows
            for selected_row, selected_weight in selected_anchor_rows
        )
        proximity = math.exp(-distance / feature_scale)
        mood, relationship = self._mood_score(candidate, selected_colors, mode)
        if scope == "spectrum":
            score = 0.23 * co_occurrence + 0.17 * cluster_affinity + 0.15 * proximity + 0.45 * mood
        else:
            score = 0.35 * co_occurrence + 0.20 * cluster_affinity + 0.15 * proximity + 0.30 * mood
        details = [relationship]
        if custom_anchor_names:
            details.append(f"Input interpreted through {', '.join(custom_anchor_names)}")
        if shared:
            details.append(f"Appears through {shared} related Wada {'combination' if shared == 1 else 'combinations'}")
        if candidate.metadata.get("generated"):
            details.append("Generated in perceptual OKLCH space")
        label = ("shared Wada group" if shared == 1 else "shared Wada groups") if shared else "model affinity"
        value = shared if shared else round(cluster_affinity * 100)
        recommendation = Recommendation(candidate, max(0.0, min(1.0, score)), label, value, tuple(details))
        return ScoredCandidate(recommendation, rgb_to_oklch(candidate.rgb), score)

    def _rerank(self, candidates: list[ScoredCandidate], mode: str, limit: int) -> list[Recommendation]:
        remaining = candidates.copy()
        chosen: list[ScoredCandidate] = []
        diversity_weight = {"quiet": 0.06, "balanced": 0.15, "vivid": 0.21}[mode]
        while remaining and len(chosen) < limit:
            def marginal(item: ScoredCandidate) -> float:
                if not chosen:
                    return item.base_score
                nearest = min(perceptual_distance(item.recommendation.color.rgb, selected.recommendation.color.rgb) for selected in chosen)
                redundancy = max(0.0, (0.13 - nearest) / 0.13)
                return item.base_score + diversity_weight * nearest - 0.12 * redundancy

            selected = max(remaining, key=marginal)
            chosen.append(selected)
            remaining.remove(selected)
        return [item.recommendation for item in chosen]

    def recommend(self, selected_colors: list[PaletteColor], mode: str = "balanced", limit: int = 4, scope: str = "palette") -> list[Recommendation]:
        if self._dataset is None or self._features is None or self._labels is None:
            raise RuntimeError("Engine must be fit before inference")
        if not selected_colors or limit <= 0:
            return []
        if mode not in {"quiet", "balanced", "vivid"}:
            raise ValueError(f"Unknown harmony mode: {mode}")
        if scope not in {"palette", "spectrum"}:
            raise ValueError(f"Unknown recommendation scope: {scope}")

        selected_anchor_rows: list[tuple[int, float]] = []
        selected_labels: set[int] = set()
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
                selected_labels.add(int(self._labels[row]))
                observed_groups.update(self._dataset.groups_by_color.get(anchor.id, frozenset()))
                excluded.add(anchor.id)

        pool = self._dataset.colors if scope == "palette" else tuple(self._spectrum_candidates(selected_colors, mode))
        scored = [
            scored_candidate
            for candidate in pool
            if candidate.id not in excluded
            for scored_candidate in [self._score_candidate(
                candidate, selected_colors, selected_anchor_rows, selected_labels, frozenset(observed_groups),
                tuple(dict.fromkeys(custom_anchor_names)), mode, scope,
            )]
            if scored_candidate is not None
        ]
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
                "validation": "deterministic 20% group holdout",
            },
            "selected": asdict(self._selected),
            "candidates": [asdict(item) for item in leaderboard],
            "metricWeights": {"silhouette": 0.30, "calinskiHarabasz": 0.15, "daviesBouldin": 0.15, "groupRecallAt10": 0.40},
        }
