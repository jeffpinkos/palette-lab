from pathlib import Path

from .adapters.group_cooccurrence_engine import GroupCooccurrenceEngine
from .adapters.grouped_json_palette import GroupedJsonPaletteProvider, JsonFieldMapping
from .domain import PaletteMetadata

ROOT = Path(__file__).parents[1]

wada_provider = GroupedJsonPaletteProvider(
    ROOT / "data" / "colors.json",
    PaletteMetadata(
        id="wada-1933", name="WADA",
        description="Choose up to four starting colors. Wada studies the company they keep.",
        source_name="Sanzo Wada", source_url="https://sanzo-wada.dmbk.io/",
        attribution="Sanzo Wada · 1933", edition_label="348 combinations",
        group_label="historic combinations",
    ),
    JsonFieldMapping(collection="colors", id="index", name="name", hex="hex", rgb="rgb_array", groups="combinations"),
    default_color_ids=("19", "112"),
)

PALETTE_PROVIDERS = {wada_provider.id: wada_provider}


def cluster_ensemble_factory():
    # Keep the baseline API importable in minimal environments; ML dependencies
    # are loaded only when this engine is selected.
    from .adapters.cluster_ensemble_engine import ClusterEnsembleEngine
    return ClusterEnsembleEngine()


ENGINE_FACTORIES = {
    GroupCooccurrenceEngine.id: GroupCooccurrenceEngine,
    "cluster-ensemble-v2": cluster_ensemble_factory,
}
