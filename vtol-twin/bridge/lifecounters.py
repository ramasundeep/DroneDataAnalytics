"""Advance the Thing's lifeCounters after an ingested sortie (idempotent per sortie id)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from common.ditto_client import DittoClient

MAX_REMEMBERED_SORTIES = 200


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def accrue_sortie(counters: Dict[str, Any], components: Iterable[str], sortie_id: str, flight_hours: float,
                  landings: int = 1, updated_at: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Pure function: returns the merge patch for the lifeCounters feature, or None if already ingested."""
    ingested = list(counters.get("ingestedSorties") or [])
    if sortie_id in ingested or counters.get("lastSortieId") == sortie_id:
        return None
    patch: Dict[str, Any] = {}
    for cid in list(components) + ["airframe"]:
        cur = counters.get(cid) or {"hours": 0.0, "cycles": 0}
        patch[cid] = {"hours": round(float(cur.get("hours", 0.0)) + flight_hours, 3),
                      "cycles": int(cur.get("cycles", 0)) + (landings if cid == "airframe" else 1)}
    ingested.append(sortie_id)
    patch["ingestedSorties"] = ingested[-MAX_REMEMBERED_SORTIES:]
    patch["lastSortieId"] = sortie_id
    patch["lastSortieHours"] = round(flight_hours, 3)
    patch["updatedAt"] = updated_at or now_iso()
    return patch


def accrue_on_thing(ditto: DittoClient, sortie_id: str, flight_hours: float, landings: int = 1) -> Optional[Dict[str, Any]]:
    components = list(ditto.get_attributes().get("components", {}).keys())
    counters = ditto.get_feature_properties("lifeCounters")
    patch = accrue_sortie(counters, components, sortie_id, flight_hours, landings)
    if patch is not None:
        ditto.merge_features({"lifeCounters": patch})
    return patch
