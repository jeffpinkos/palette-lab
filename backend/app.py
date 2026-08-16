from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .registry import ENGINE_FACTORIES, PALETTE_PROVIDERS
from .service import RecommendationService

app = FastAPI(title="Palette Harmony API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
service = RecommendationService(PALETTE_PROVIDERS, ENGINE_FACTORIES)


class HarmonyRequest(BaseModel):
    palette_id: str
    engine_id: str
    color_ids: list[str] = Field(min_length=1, max_length=4)
    mode: Literal["quiet", "balanced", "vivid"] = "balanced"
    limit: int = Field(default=4, ge=1, le=12)


@app.get("/api/health")
def health():
    return {"status": "ok", "palettes": service.palette_ids, "engines": service.engine_ids}


@app.get("/api/palettes")
def palettes():
    return {"palettes": [service.dataset(palette_id).metadata.as_dict() for palette_id in service.palette_ids]}


@app.post("/api/recommend")
def recommend(request: HarmonyRequest):
    try:
        recommendations = service.recommend(request.palette_id, request.engine_id, request.color_ids, request.mode, request.limit)
    except (KeyError, ValueError) as error:
        raise HTTPException(400, str(error)) from error
    return {"recommendations": [recommendation.as_dict() for recommendation in recommendations]}
