"""CD Sim assessment engine (FastAPI).

Phase 0 scope: health, rubric catalogue, rubric validation, and scoring of
caller-supplied metric values against a rubric (``POST /v1/score``). Deriving
metric values from recorded sessions, audio analysis and PDF reports arrive
in Phase 3 (docs/06_ASSESSMENT_ENGINE.md, docs/10_ROADMAP.md).

Run locally:  uvicorn --factory cdsim_assessment.main:create_app --port 8002
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel

from cdsim_assessment import __version__
from cdsim_assessment.scoring import RubricResult, score_rubric
from cdsim_common.config import Settings, get_settings
from cdsim_common.deps import postgres_check, redis_check
from cdsim_common.health import Check, health_router
from cdsim_common.manifests import (
    ManifestKind,
    discover,
    rubric_semantic_errors,
    schema_errors,
)

SERVICE = "assessment"
log = logging.getLogger(__name__)


class ScoreRequest(BaseModel):
    rubric_id: str
    values: dict[str, float | None]


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str]


def create_app(settings: Settings | None = None, with_infra_checks: bool = True) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    found, errors = discover(settings.schemas_dir, rubrics_dir=settings.rubrics_dir)
    for err in errors:
        log.error("invalid rubric %s", err)

    async def rubrics_ok() -> None:
        if errors:
            raise RuntimeError(f"{len(errors)} invalid rubric(s)")

    checks: dict[str, Check] = {"rubrics": rubrics_ok}
    if with_infra_checks:
        checks |= {"postgres": postgres_check(settings), "redis": redis_check(settings)}

    app = FastAPI(title="CD Sim Assessment", version=__version__)
    app.state.rubrics = found.rubrics
    app.state.settings = settings
    app.include_router(health_router(SERVICE, __version__, checks))
    app.include_router(_router())
    return app


def _router() -> APIRouter:
    r = APIRouter(prefix="/v1", tags=["assessment"])

    @r.get("/rubrics")
    async def list_rubrics(request: Request) -> list[dict[str, Any]]:
        return list(request.app.state.rubrics.values())

    @r.post("/rubrics/validate", response_model=ValidationResult)
    async def validate(rubric: dict[str, Any], request: Request) -> ValidationResult:
        settings: Settings = request.app.state.settings
        errs = schema_errors(rubric, ManifestKind.RUBRIC, settings.schemas_dir)
        if not errs:
            errs = rubric_semantic_errors(rubric)
        return ValidationResult(valid=not errs, errors=errs)

    @r.post("/score", response_model=RubricResult)
    async def score(req: ScoreRequest, request: Request) -> RubricResult:
        rubric = request.app.state.rubrics.get(req.rubric_id)
        if rubric is None:
            raise HTTPException(404, f"rubric '{req.rubric_id}' not found")
        return score_rubric(rubric, req.values)

    @r.post("/sessions/{session_id}/assess")
    async def assess(session_id: str) -> None:
        raise HTTPException(501, "Session assessment is scheduled for Phase 3")

    return r
