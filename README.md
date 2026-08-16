# Palette Laboratory

A decoupled React + TypeScript color laboratory with pluggable palette providers and recommendation engines. The included Wada configuration is grounded in the 157 colors and 348 historic combinations from the [Sanzo Wada dataset](https://sanzo-wada.dmbk.io/assets/colors.json).

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

Implement `RecommendationEngine`. The frontend engine receives a normalized dataset plus selected color IDs; the Python engine has explicit `fit(dataset)` and `recommend(...)` stages. Register remote engines in `backend/registry.py` and select the desired engine in the frontend composition root.

`ApiRecommendationEngine` is already available when inference should run exclusively in Python instead of in the browser.

## Run

```bash
npm install
npm run dev
```

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload
```

The generic API request is:

```json
{
  "palette_id": "wada-1933",
  "engine_id": "group-cooccurrence-v1",
  "color_ids": ["19", "112"],
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

Run all 100 unit cases together with `npm run test:all`; use `npm run test:watch` while developing TypeScript modules.
