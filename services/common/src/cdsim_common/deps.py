"""Readiness checks for the shared infrastructure (Postgres, Redis, MinIO).

Each factory returns an async ``Check`` for ``health_router``. The blocking
client libraries are called in a worker thread so a slow dependency never
stalls the event loop; ``health_router`` applies a timeout on top.
"""

from __future__ import annotations

import asyncio

from cdsim_common.config import Settings
from cdsim_common.health import Check


def postgres_check(settings: Settings) -> Check:
    async def check() -> None:
        import psycopg

        async with await psycopg.AsyncConnection.connect(
            settings.db_dsn, connect_timeout=2
        ) as conn:
            cur = await conn.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"
            )
            if await cur.fetchone() is None:
                raise RuntimeError("timescaledb extension not installed")

    return check


def redis_check(settings: Settings) -> Check:
    async def check() -> None:
        import redis.asyncio as aioredis

        client = aioredis.from_url(  # type: ignore[no-untyped-call]
            settings.redis_url, socket_connect_timeout=2
        )
        try:
            await client.ping()
        finally:
            await client.aclose()

    return check


def minio_check(settings: Settings, bucket: str | None = None) -> Check:
    async def check() -> None:
        from minio import Minio

        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key.get_secret_value(),
            secure=settings.minio_secure,
        )
        target = bucket or settings.recordings_bucket
        exists = await asyncio.to_thread(client.bucket_exists, target)
        if not exists:
            raise RuntimeError(f"bucket '{target}' missing")

    return check
