# Palette Laboratory

A decoupled React + TypeScript color laboratory with pluggable palette providers and recommendation engines. The included Wada configuration is grounded in the 157 colors and 348 historic combinations from the [Sanzo Wada dataset](https://sanzo-wada.dmbk.io/assets/colors.json).

Users may search 31,914 curated color names or enter and pick any six-digit color. Exact custom values remain in the composition, receive the closest perceptual name from the MIT-licensed [Color Name List](https://www.npmjs.com/package/color-name-list), and let the ML engine interpolate four nearby training anchors. Results can stay inside the source archive or explore named, generated OKLCH colors across the full spectrum.

## Architecture

```text
source data -> PaletteProvider -> PaletteDataset -> RecommendationEngine -> ColorNamer -> React UI
```

- `src/domain/` contains source- and model-independent types.
- `src/contracts/` defines the provider and engine ports.
- `ColorNamer` is a separate port, so other name catalogs can replace the bundled full list without changing palette or ML code.
- `src/adapters/palettes/` normalizes individual palette sources.
- `src/adapters/engines/` contains local and remote inference adapters.
- `src/config/runtime.ts` is the frontend composition root.
- `backend/contracts.py` and `backend/domain.py` define the equivalent Python ports.
- `backend/registry.py` is the backend composition root.
- `backend/service.py` caches normalized datasets and fitted engine instances by palette and engine ID.

The React UI does not import Wada fields, group IDs, or a particular ML implementation. The Python API accepts both `palette_id` and `engine_id`, so either dimension can vary independently.

## Add another palette

Implement `PaletteProvider` and return the normalized `PaletteDataset`, then select it in `src/config/runtime.ts`. Group-based engines need `groupsByColor`; embedding or remote engines may ignore it.

For grouped JSON sources, the backend's `GroupedJsonPaletteProvider` can adapt a new schema with field mappings instead of a new loader. Register the provider in `backend/registry.py`.

## Add another ML engine

Implement `RecommendationEngine`. The frontend engine receives a normalized dataset plus the user's exact selected colors; the Python engine has explicit `fit(dataset)` and `recommend(...)` stages. Engines may project arbitrary colors onto palette anchors for training signals without replacing the user's input. Register remote engines in `backend/registry.py` and select the desired engine in the frontend composition root.

`ApiRecommendationEngine` is already available when inference should run exclusively in Python instead of in the browser.

## Evaluated clustering engine

The backend includes `cluster-ensemble-v2`, an optimized model-selection pipeline that:

1. Builds a block-normalized feature matrix from rotation-equivariant OKLab values and an eight-dimensional SVD of L2-normalized TF-IDF historical-group vectors. Lightness is scaled separately while the chromatic `a/b` plane uses one isotropic scale.
2. Trains optimized K-means, Ward agglomerative clustering, and regularized full-covariance Gaussian mixtures across several cluster counts, preserving co-membership when the complete color geometry is rotated.
3. Holds out a seeded 20% of palette groups and measures recall and NDCG at 10 alongside silhouette, Calinski–Harabasz, and Davies–Bouldin scores.
4. Combines outlier-resistant percentile ranks with a small parsimony term to select the best model without over-rewarding excess clusters.
5. Calibrates soft-cluster temperature against held-out NDCG; for Wada, the validated rotation-equivariant K-means-10 model is the ranking backbone while Ward and Gaussian-mixture models provide candidate-level rank confidence.
6. Learns support and contrast relationship archetypes from unique historical color pairs and includes their empirical mixture likelihood in every recommendation score.
7. Scores explicit OKLCH color-wheel harmonies—monochromatic, analogous, tetradic, triadic, split-complementary, and complementary—with mode-sensitive emphasis and tonal handling for neutrals.
8. Projects arbitrary colors through an adaptive four-neighbor Gaussian kernel and compares calibrated cluster, TF-IDF group, feature-centroid, historical-relation, classical-harmony, and perceptual-mood vectors.
9. Uses a greedy determinantal point process objective to avoid redundant suggestions, plus hue-preserving OKLCH gamut mapping for generated colors.

Recommendation evidence includes historic overlap, hue interval and lightness contrast, cross-model rank agreement, support/contrast fit, custom-input anchor names, and generated-color provenance. Model diagnostics expose the calibrated family ensemble, learned relation mixture, and recommendation score weights. The interface can add a suggestion back into the composition, copy individual hex values or the complete CSS palette, and export a CSS file.

Training is deterministic through a fixed random seed. Inspect the full candidate leaderboard and selected model at:

```text
GET /api/models/wada-1933/cluster-ensemble-v2
```

## Run

```bash
npm install
npm run dev
```

Run the ML API in a second terminal with `npm run dev:api`. The frontend is configured to use `cluster-ensemble-v2` through Vite's `/api` proxy.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
uvicorn backend.app:app --reload
```

The ML backend requires Python 3.11 or newer; `.python-version` selects Python 3.12.

The generic API request is:

```json
{
  "palette_id": "wada-1933",
  "engine_id": "cluster-ensemble-v2",
  "colors": [
    { "id": "custom:#12abef", "name": "Custom color", "hex": "#12abef", "rgb": [18, 171, 239] }
  ],
  "mode": "balanced",
  "scope": "spectrum",
  "limit": 4
}
```

## Verify

```bash
npm test
npm run build
python -m pytest backend/test_architecture.py
```

Run all 201 unit cases together with `npm run test:all`; use `npm run test:watch` while developing TypeScript modules.
