# Palette Laboratory

A decoupled React + TypeScript color laboratory with pluggable palette providers and recommendation engines. The included Wada configuration is grounded in the 157 colors and 348 historic combinations from the [Sanzo Wada dataset](https://sanzo-wada.dmbk.io/assets/colors.json).

Users may enter or pick any six-digit color. Exact custom RGB values remain in the composition while recommendation engines use the active palette only as a source of learned harmony signals.

## Architecture

```text
source data -> PaletteProvider -> PaletteDataset -> RecommendationEngine -> React UI
```

- `src/domain/` contains source- and model-independent types.
- `src/contracts/` defines the provider and engine ports.
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

The backend includes `cluster-ensemble-v1`, an actual model-selection pipeline that:

1. Builds a standardized feature matrix from RGB values and a Truncated SVD embedding of palette group/co-occurrence signals.
2. Trains K-means, Ward agglomerative clustering, and diagonal-covariance Gaussian mixtures across several cluster counts.
3. Evaluates every candidate with silhouette, Calinski–Harabasz, and Davies–Bouldin scores.
4. Normalizes those metrics into a weighted composite and retains the best candidate.
5. Blends learned cluster membership, historical co-occurrence, feature proximity, and the selected color mood when ranking recommendations.

Training is deterministic through a fixed random seed. Inspect the full candidate leaderboard and selected model at:

```text
GET /api/models/wada-1933/cluster-ensemble-v1
```

## Run

```bash
npm install
npm run dev
```

Run the ML API in a second terminal with `npm run dev:api`. The frontend is configured to use `cluster-ensemble-v1` through Vite's `/api` proxy.

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
  "engine_id": "group-cooccurrence-v1",
  "colors": [
    { "id": "custom:#12abef", "name": "Custom color", "hex": "#12abef", "rgb": [18, 171, 239] }
  ],
  "mode": "balanced",
  "limit": 4
}
```

## Verify

```bash
npm test
npm run build
python -m pytest backend/test_architecture.py
```

Run all 133 unit cases together with `npm run test:all`; use `npm run test:watch` while developing TypeScript modules.
