import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo


TOKENS_PATH = Path("./secrets/strava_tokens.json")
GEAR_CACHE_PATH = Path("./secrets/gear_cache.json")
LOCAL_TIMEZONE_DEFAULT = "Australia/Melbourne"


@dataclass
class StravaEnv:
    client_id: str
    client_secret: str


@dataclass
class IntervalsEnv:
    api_key: str
    athlete_id: int = 0


def load_env() -> StravaEnv:
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    missing = []
    if not client_id:
        missing.append("STRAVA_CLIENT_ID")
    if not client_secret:
        missing.append("STRAVA_CLIENT_SECRET")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    return StravaEnv(client_id=client_id, client_secret=client_secret)


def load_intervals_env() -> IntervalsEnv:
    api_key = os.getenv("INTERVALS_API_KEY")
    if not api_key:
        raise RuntimeError("Missing required environment variable: INTERVALS_API_KEY")
    athlete_id_raw = os.getenv("INTERVALS_ATHLETE_ID", "0")
    try:
        athlete_id = int(athlete_id_raw)
    except ValueError as exc:
        raise RuntimeError("INTERVALS_ATHLETE_ID must be an integer") from exc
    return IntervalsEnv(api_key=api_key, athlete_id=athlete_id)


def _ensure_secrets_dir() -> None:
    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_tokens() -> Dict[str, Any]:
    if TOKENS_PATH.exists():
        with TOKENS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_tokens(tokens: Dict[str, Any]) -> None:
    _ensure_secrets_dir()
    with TOKENS_PATH.open("w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)


def load_gear_cache() -> Dict[str, str]:
    if GEAR_CACHE_PATH.exists():
        with GEAR_CACHE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_gear_cache(cache: Dict[str, str]) -> None:
    _ensure_secrets_dir()
    with GEAR_CACHE_PATH.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def get_token_value(tokens: Dict[str, Any], key: str) -> Optional[Any]:
    value = tokens.get(key)
    return value if value is not None else None


def load_local_timezone() -> ZoneInfo:
    name = os.getenv("LOCAL_TIMEZONE")
    if name:
        try:
            return ZoneInfo(name)
        except Exception:
            print(
                f"Invalid LOCAL_TIMEZONE='{name}' - falling back to {LOCAL_TIMEZONE_DEFAULT}"
            )
    return ZoneInfo(LOCAL_TIMEZONE_DEFAULT)
