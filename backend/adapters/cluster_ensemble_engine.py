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

from ..domain import PaletteColor, PaletteDataset, Recommendation


@dataclass
class ClusterEvaluation:
    algorithm: str
    clusters: int
    silhouette: float
    calinski_harabasz: float
    davies_bouldin: float
    composite: float = 0.0


class ClusterEnsembleEngine:
    """Selects a clustering model, then blends cluster and historical affinity."""

    id = "cluster-ensemble-v1"
    name = "Evaluated clustering ensemble"

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
    def _rgb_distance(left: PaletteColor, right: PaletteColor) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(left.rgb, right.rgb))) / 441.67

    def _feature_matrix(self, dataset: PaletteDataset) -> np.ndarray:
        rgb = np.asarray([color.rgb for color in dataset.colors], dtype=float) / 255.0
        group_ids = sorted({group for groups in dataset.groups_by_color.values() for group in groups})
        if len(group_ids) < 2:
            return StandardScaler().fit_transform(rgb)

        group_columns = {group_id: index for index, group_id in enumerate(group_ids)}
        incidence = np.zeros((len(dataset.colors), len(group_ids)), dtype=float)
        for row, color in enumerate(dataset.colors):
            for group_id in dataset.groups_by_color.get(color.id, frozenset()):
                incidence[row, group_columns[group_id]] = 1.0

        component_count = min(12, len(dataset.colors) - 1, len(group_ids) - 1)
        embedding = TruncatedSVD(n_components=component_count, random_state=self._random_state).fit_transform(incidence)
        return StandardScaler().fit_transform(np.hstack((rgb * 0.75, embedding)))

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

    def fit(self, dataset: PaletteDataset) -> None:
        if len(dataset.colors) < 4:
            raise ValueError("Cluster ensemble requires at least four colors")
        self._dataset = dataset
        self._colors_by_id = {color.id: color for color in dataset.colors}
        self._row_by_id = {color.id: row for row, color in enumerate(dataset.colors)}
        self._features = self._feature_matrix(dataset)
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
                        if not 2 <= len(np.unique(labels)) < len(dataset.colors):
                            continue
                        evaluation = ClusterEvaluation(
                            algorithm=algorithm,
                            clusters=clusters,
                            silhouette=float(silhouette_score(self._features, labels)),
                            calinski_harabasz=float(calinski_harabasz_score(self._features, labels)),
                            davies_bouldin=float(davies_bouldin_score(self._features, labels)),
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
        for index, evaluation in enumerate(self._evaluations):
            evaluation.composite = 0.5 * silhouettes[index] + 0.3 * calinski[index] + 0.2 * davies[index]
        self._selected = max(self._evaluations, key=lambda item: (item.composite, item.silhouette))
        self._labels = labels_by_candidate[(self._selected.algorithm, self._selected.clusters)]

    def _nearest_anchor(self, selected: PaletteColor) -> PaletteColor:
        known = self._colors_by_id.get(selected.id)
        return known or min(self._dataset.colors, key=lambda candidate: self._rgb_distance(selected, candidate))  # type: ignore[union-attr]

    def recommend(self, selected_colors: list[PaletteColor], mode: str = "balanced", limit: int = 4) -> list[Recommendation]:
        if self._dataset is None or self._features is None or self._labels is None:
            raise RuntimeError("Engine must be fit before inference")
        if not selected_colors:
            return []
        anchors = [self._nearest_anchor(color) for color in selected_colors]
        anchor_rows = [self._row_by_id[color.id] for color in anchors]
        anchor_labels = {int(self._labels[row]) for row in anchor_rows}
        observed = frozenset().union(*(self._dataset.groups_by_color.get(color.id, frozenset()) for color in anchors))
        excluded = {color.id for color in selected_colors} | {color.id for color in anchors}
        scored = []
        feature_scale = math.sqrt(self._features.shape[1])

        for candidate in self._dataset.colors:
            if candidate.id in excluded:
                continue
            row = self._row_by_id[candidate.id]
            cluster_match = int(int(self._labels[row]) in anchor_labels)
            groups = self._dataset.groups_by_color.get(candidate.id, frozenset())
            shared = len(groups & observed)
            if not cluster_match and not shared:
                continue
            co_occurrence = shared / math.sqrt(max(1, len(groups) * len(observed)))
            feature_distance = float(np.mean([np.linalg.norm(self._features[row] - self._features[anchor_row]) for anchor_row in anchor_rows]))
            proximity = math.exp(-feature_distance / max(feature_scale, 1.0))
            color_distance = sum(self._rgb_distance(candidate, selected) for selected in selected_colors) / len(selected_colors)
            mood = 1 - color_distance if mode == "quiet" else color_distance if mode == "vivid" else 1 - abs(color_distance - 0.52)
            score = 0.45 * co_occurrence + 0.30 * cluster_match + 0.10 * proximity + 0.15 * mood
            scored.append(Recommendation(candidate, score, "cluster match", cluster_match))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]

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
            },
            "selected": asdict(self._selected),
            "candidates": [asdict(item) for item in leaderboard],
            "metricWeights": {"silhouette": 0.5, "calinskiHarabasz": 0.3, "daviesBouldin": 0.2},
        }
