"""Small Ditto REST client (HTTP API 2) for the VTOL-1 Thing.

Goes through the nginx front, so plain basic auth; the subject becomes nginx:<user> in policies.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx

MERGE = "application/merge-patch+json"


class DittoClient:
    def __init__(self, base_url: str, user: str, password: str, thing_id: str,
                 timeout: float = 15.0, transport: Optional[httpx.BaseTransport] = None):
        self.base_url = base_url.rstrip("/")
        self.thing_id = thing_id
        self._client = httpx.Client(base_url=self.base_url, auth=(user, password), timeout=timeout,
                                    transport=transport)

    # ---------------------------------------------------------------- reads
    def get_thing(self, fields: Optional[str] = None) -> Dict[str, Any]:
        params = {"fields": fields} if fields else None
        r = self._client.get(f"/api/2/things/{self.thing_id}", params=params)
        r.raise_for_status()
        return r.json()

    def get_feature_properties(self, feature: str) -> Dict[str, Any]:
        r = self._client.get(f"/api/2/things/{self.thing_id}/features/{feature}/properties")
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()

    def get_attributes(self) -> Dict[str, Any]:
        r = self._client.get(f"/api/2/things/{self.thing_id}/attributes")
        r.raise_for_status()
        return r.json()

    # --------------------------------------------------------------- writes
    def merge_features(self, patch: Dict[str, Dict[str, Any]]) -> None:
        """patch: {featureId: {properties...}} - JSON merge patch, null deletes."""
        body = {fid: {"properties": props} for fid, props in patch.items()}
        r = self._client.patch(f"/api/2/things/{self.thing_id}/features",
                               content=json.dumps(body), headers={"Content-Type": MERGE})
        r.raise_for_status()

    def merge_attributes(self, patch: Dict[str, Any]) -> None:
        r = self._client.patch(f"/api/2/things/{self.thing_id}/attributes",
                               content=json.dumps(patch), headers={"Content-Type": MERGE})
        r.raise_for_status()

    def health(self) -> bool:
        try:
            return self._client.get("/health").status_code == 200
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        self._client.close()
