"""Event storage and live fan-out.

``EventStore`` persists events; ``EventPublisher`` pushes them to live
subscribers (instructor console, assessment engine) via Redis pub/sub.
Both are protocols so the service can be unit-tested with in-memory fakes and
the production implementations stay thin.

Reads always return events in canonical order: (sim_time_us, seq).
"""

from __future__ import annotations

import json
from typing import Protocol

from cdsim_common.events import Event, EventFamily


class EventStore(Protocol):
    async def write(self, events: list[Event]) -> int: ...

    async def read(
        self,
        session_id: str,
        family: EventFamily | None = None,
        from_us: int | None = None,
        to_us: int | None = None,
    ) -> list[Event]: ...


class EventPublisher(Protocol):
    async def publish(self, events: list[Event]) -> None: ...


def channel_for(session_id: str) -> str:
    """Redis channel carrying live events of one session."""
    return f"cdsim.session.{session_id}.events"


# --------------------------------------------------------------- in-memory


class InMemoryEventStore:
    """Test / single-process store. Idempotent on event_id."""

    def __init__(self) -> None:
        self._events: dict[str, Event] = {}

    async def write(self, events: list[Event]) -> int:
        new = 0
        for ev in events:
            if ev.event_id not in self._events:
                self._events[ev.event_id] = ev
                new += 1
        return new

    async def read(
        self,
        session_id: str,
        family: EventFamily | None = None,
        from_us: int | None = None,
        to_us: int | None = None,
    ) -> list[Event]:
        out = [
            e
            for e in self._events.values()
            if e.header.session_id == session_id
            and (family is None or e.family is family)
            and (from_us is None or e.header.sim_time_us >= from_us)
            and (to_us is None or e.header.sim_time_us <= to_us)
        ]
        return sorted(out, key=Event.sort_key)


class NullPublisher:
    async def publish(self, events: list[Event]) -> None:
        return None


class ListPublisher:
    """Test publisher that remembers what it published."""

    def __init__(self) -> None:
        self.published: list[Event] = []

    async def publish(self, events: list[Event]) -> None:
        self.published.extend(events)


# --------------------------------------------------------------- production


class PostgresEventStore:
    """TimescaleDB-backed store (schema: services/recorder/db/001_init.sql)."""

    _INSERT = (
        "INSERT INTO events (session_id, sim_time_us, seq, wall_time_us, event_id, "
        "related_event_id, actor_id, source, family, code, body) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT DO NOTHING"
    )

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def write(self, events: list[Event]) -> int:
        import psycopg

        rows = [
            (
                e.header.session_id,
                e.header.sim_time_us,
                e.header.seq,
                e.header.wall_time_us,
                e.event_id,
                e.related_event_id,
                e.header.actor_id,
                e.header.source.value,
                e.family.value,
                e.code,
                json.dumps(e.to_proto_json()),
            )
            for e in events
        ]
        async with await psycopg.AsyncConnection.connect(self._dsn) as conn:
            async with conn.cursor() as cur:
                await cur.executemany(self._INSERT, rows)
            await conn.commit()
        return len(rows)

    async def read(
        self,
        session_id: str,
        family: EventFamily | None = None,
        from_us: int | None = None,
        to_us: int | None = None,
    ) -> list[Event]:
        import psycopg

        sql = "SELECT body FROM events WHERE session_id = %s"
        args: list[object] = [session_id]
        if family is not None:
            sql += " AND family = %s"
            args.append(family.value)
        if from_us is not None:
            sql += " AND sim_time_us >= %s"
            args.append(from_us)
        if to_us is not None:
            sql += " AND sim_time_us <= %s"
            args.append(to_us)
        sql += " ORDER BY sim_time_us, seq"
        async with await psycopg.AsyncConnection.connect(self._dsn) as conn:
            cur = await conn.execute(sql, args)
            rows = await cur.fetchall()
        return [Event.model_validate(r[0]) for r in rows]


class RedisPublisher:
    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(url)  # type: ignore[no-untyped-call]

    async def publish(self, events: list[Event]) -> None:
        async with self._client.pipeline(transaction=False) as pipe:
            for e in events:
                pipe.publish(channel_for(e.header.session_id), json.dumps(e.to_proto_json()))
            await pipe.execute()
