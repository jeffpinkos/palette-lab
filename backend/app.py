from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .domain import PaletteColor
from .registry import ENGINE_FACTORIES, PALETTE_PROVIDERS
from .service import RecommendationService

app = FastAPI(title="Palette Harmony API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
service = RecommendationService(PALETTE_PROVIDERS, ENGINE_FACTORIES)


class ColorInput(BaseModel):
    id: str
    name: str = "Custom color"
    hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    rgb: tuple[int, int, int]


class HarmonyRequest(BaseModel):
    palette_id: str
    engine_id: str
    colors: list[ColorInput] = Field(min_length=1, max_length=4)
    mode: Literal["quiet", "balanced", "vivid"] = "balanced"
    scope: Literal["companions", "palette", "spectrum"] = "palette"
    limit: int = Field(default=4, ge=1, le=12)


class PaletteAssessmentRequest(BaseModel):
    palette_id: str
    engine_id: str
    colors: list[ColorInput] = Field(min_length=1, max_length=4)


@app.get("/api/health")
def health():
    return {"status": "ok", "palettes": service.palette_ids, "engines": service.engine_ids}


@app.get("/api/palettes")
def palettes():
    return {"palettes": [service.dataset(palette_id).metadata.as_dict() for palette_id in service.palette_ids]}


@app.get("/api/models/{palette_id}/{engine_id}")
def model_diagnostics(palette_id: str, engine_id: str):
    try:
        return service.diagnostics(palette_id, engine_id)
    except (KeyError, ValueError) as error:
        raise HTTPException(400, str(error)) from error


@app.post("/api/recommend")
def recommend(request: HarmonyRequest):
    try:
        selected = [PaletteColor(color.id, color.name, color.hex.lower(), color.rgb, {"custom": color.id.startswith("custom:")}) for color in request.colors]
        recommendations = service.recommend(request.palette_id, request.engine_id, selected, request.mode, request.limit, request.scope)
    except (KeyError, ValueError) as error:
        raise HTTPException(400, str(error)) from error
    return {"recommendations": [recommendation.as_dict() for recommendation in recommendations]}


@app.post("/api/assess")
def assess(request: PaletteAssessmentRequest):
    try:
        selected = [PaletteColor(color.id, color.name, color.hex.lower(), color.rgb, {"custom": color.id.startswith("custom:")}) for color in request.colors]
        assessment = service.assess(request.palette_id, request.engine_id, selected)
    except (KeyError, ValueError) as error:
        raise HTTPException(400, str(error)) from error
    return {"assessment": assessment.as_dict() if assessment else None}
