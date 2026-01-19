import random
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx


class StravaClient:
    def __init__(self, access_token: str, debug: bool = False) -> None:
        self.access_token = access_token
        self.debug = debug
        self.base_url = "https://www.strava.com/api/v3"
        self._client = httpx.Client(timeout=30)

    def close(self) -> None:
        self._client.close()

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    def _maybe_sleep_for_rate_limit(self, headers: Dict[str, str]) -> None:
        usage = headers.get("X-RateLimit-Usage")
        limit = headers.get("X-RateLimit-Limit")
        if not usage or not limit:
            return
        try:
            usage_short, usage_long = [int(x) for x in usage.split(",")]
            limit_short, limit_long = [int(x) for x in limit.split(",")]
        except ValueError:
            return
        near_short = usage_short / max(limit_short, 1) >= 0.9
        near_long = usage_long / max(limit_long, 1) >= 0.9
        if near_short or near_long:
            time.sleep(2)

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        retry_statuses = {429, 500, 502, 503, 504}
        last_exc: Optional[Exception] = None
        for attempt in range(5):
            try:
                resp = self._client.request(
                    method, url, params=params, headers=self._headers()
                )
                if resp.status_code in retry_statuses:
                    sleep_s = min(2 ** attempt, 30) + random.uniform(0, 0.5)
                    time.sleep(sleep_s)
                    continue
                resp.raise_for_status()
                self._maybe_sleep_for_rate_limit(resp.headers)
                return resp
            except httpx.RequestError as exc:
                last_exc = exc
                sleep_s = min(2 ** attempt, 30) + random.uniform(0, 0.5)
                time.sleep(sleep_s)
        if last_exc:
            raise RuntimeError(f"Network error contacting Strava: {last_exc}") from last_exc
        raise RuntimeError("Failed to contact Strava after retries.")

    def list_activities(self, after_epoch: int, before_epoch: int) -> List[Dict[str, Any]]:
        page = 1
        per_page = 200
        activities: List[Dict[str, Any]] = []
        while True:
            params = {
                "after": after_epoch,
                "before": before_epoch,
                "per_page": per_page,
                "page": page,
            }
            resp = self.request("GET", "/athlete/activities", params=params)
            data = resp.json()
            if not data:
                break
            activities.extend(data)
            page += 1
        return activities

    def get_gear(self, gear_id: str) -> Dict[str, Any]:
        resp = self.request("GET", f"/gear/{gear_id}")
        return resp.json()

    def get_activity_detail(self, activity_id: int) -> Dict[str, Any]:
        resp = self.request("GET", f"/activities/{activity_id}")
        return resp.json()
