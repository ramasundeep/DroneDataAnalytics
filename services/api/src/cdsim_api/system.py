"""Aggregate health of every CD Sim service, for the instructor console."""

from __future__ import annotations

import asyncio
import time
from typing import Literal

import httpx
from pydantic import BaseModel

ServiceStatus = Literal["ok", "degraded", "unreachable"]


class ServiceHealth(BaseModel):
    name: str
    url: str
    status: ServiceStatus
    detail: str = ""
    latency_ms: float = 0.0


class SystemHealth(BaseModel):
    status: Literal["ok", "degraded"]
    services: list[ServiceHealth]


async def _probe(client: httpx.AsyncClient, name: str, url: str) -> ServiceHealth:
    start = time.perf_counter()
    try:
        resp = await client.get(f"{url}/ready")
    except httpx.HTTPError as exc:
        return ServiceHealth(name=name, url=url, status="unreachable", detail=type(exc).__name__)
    latency = (time.perf_counter() - start) * 1e3
    if resp.status_code == 200:
        return ServiceHealth(name=name, url=url, status="ok", latency_ms=latency)
    detail = ""
    try:
        failed = [k for k, v in resp.json().get("checks", {}).items() if not v.get("ok")]
        detail = "failed checks: " + ", ".join(failed) if failed else f"HTTP {resp.status_code}"
    except ValueError:
        detail = f"HTTP {resp.status_code}"
    return ServiceHealth(name=name, url=url, status="degraded", detail=detail, latency_ms=latency)


async def probe_all(
    services: dict[str, str], transport: httpx.AsyncBaseTransport | None = None
) -> SystemHealth:
    async with httpx.AsyncClient(timeout=3.0, transport=transport) as client:
        results = await asyncio.gather(*(_probe(client, n, u) for n, u in services.items()))
    overall: Literal["ok", "degraded"] = (
        "ok" if all(r.status == "ok" for r in results) else "degraded"
    )
    return SystemHealth(status=overall, services=list(results))
