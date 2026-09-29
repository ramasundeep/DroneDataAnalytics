"""Standard health endpoints shared by every CD Sim HTTP service.

* ``GET /health`` — liveness: the process is up. Always 200.
* ``GET /ready``  — readiness: every dependency check passes. 200 or 503.

Docker Compose health checks call ``/ready`` so that "healthy" in
``docker compose ps`` means the service can actually do its job. The API
aggregates every service's ``/ready`` for the instructor console.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping

from fastapi import APIRouter, Response
from pydantic import BaseModel

Check = Callable[[], Awaitable[None]]
"""A readiness check: returns normally if OK, raises with a reason if not."""

CHECK_TIMEOUT_S = 2.0


class CheckResult(BaseModel):
    ok: bool
    detail: str = ""
    latency_ms: float = 0.0


class HealthReport(BaseModel):
    service: str
    version: str
    status: str  # "ok" | "degraded"
    checks: dict[str, CheckResult] = {}


async def _run_check(check: Check) -> CheckResult:
    start = time.perf_counter()
    try:
        await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_S)
    except Exception as exc:
        return CheckResult(
            ok=False,
            detail=f"{type(exc).__name__}: {exc}"[:300],
            latency_ms=(time.perf_counter() - start) * 1e3,
        )
    return CheckResult(ok=True, latency_ms=(time.perf_counter() - start) * 1e3)


def health_router(
    service: str, version: str, checks: Mapping[str, Check] | None = None
) -> APIRouter:
    """Build the /health and /ready routes for a service."""
    router = APIRouter(tags=["health"])
    checks = dict(checks or {})

    @router.get("/health", response_model=HealthReport)
    async def health() -> HealthReport:
        return HealthReport(service=service, version=version, status="ok")

    @router.get("/ready", response_model=HealthReport)
    async def ready(response: Response) -> HealthReport:
        names = list(checks)
        results = await asyncio.gather(*(_run_check(checks[n]) for n in names))
        report = HealthReport(
            service=service,
            version=version,
            status="ok" if all(r.ok for r in results) else "degraded",
            checks=dict(zip(names, results, strict=True)),
        )
        if report.status != "ok":
            response.status_code = 503
        return report

    return router
