import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dateutil import parser

from .config import load_gear_cache, save_gear_cache
from .strava_client import StravaClient


RUN_TYPES = {
    "easy",
    "long",
    "progression",
    "tempo",
    "intervals",
    "recovery",
    "race",
    "unknown",
}

RIDE_TYPES = {
    "outdoor_endurance",
    "zwift_tempo",
    "zwift_intervals",
    "recovery",
    "race",
    "unknown",
}


def _round_1(value: float) -> float:
    return round(value + 1e-9, 1)


def _format_pace(minutes_per_km: float) -> str:
    total_seconds = int(round(minutes_per_km * 60))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _generic_name(name: str, activity_type: str) -> bool:
    if not name:
        return True
    lower = name.strip().lower()
    base = activity_type.lower()
    generic_patterns = {
        f"{base}",
        f"morning {base}",
        f"afternoon {base}",
        f"evening {base}",
        f"lunch {base}",
        f"night {base}",
    }
    return lower in generic_patterns


def _activity_date(activity: Dict[str, Any]) -> date:
    start_local = activity.get("start_date_local")
    return parser.isoparse(start_local).date()


def _run_type(activity: Dict[str, Any]) -> str:
    workout_type = activity.get("workout_type")
    name = (activity.get("name") or "").lower()
    if workout_type == 1:
        return "race"
    if workout_type == 2:
        return "long"
    if workout_type == 3:
        return "intervals"
    if "tempo" in name:
        return "tempo"
    if "interval" in name or "vo2" in name:
        return "intervals"
    if "progression" in name:
        return "progression"
    if "recovery" in name:
        return "recovery"
    if "easy" in name:
        return "easy"
    if "race" in name:
        return "race"
    distance_km = (activity.get("distance") or 0) / 1000.0
    if distance_km >= 20:
        return "long"
    return "unknown"


def _ride_type(activity: Dict[str, Any]) -> str:
    name = (activity.get("name") or "").lower()
    if activity.get("trainer"):
        return "zwift_tempo" if "zwift" in name else "unknown"
    if activity.get("commute"):
        if "interval" in name or "vo2" in name:
            return "zwift_intervals"
        return "recovery"
    if "race" in name:
        return "race"
    return "outdoor_endurance"


def _activity_notes(activity: Dict[str, Any], activity_type: str) -> str:
    name = activity.get("name") or ""
    activity_id = activity.get("id")
    if _generic_name(name, activity_type):
        return f"(strava_id: {activity_id})"
    return f"{name} (strava_id: {activity_id})"


def _activity_description(detail: Dict[str, Any]) -> str:
    description = detail.get("description")
    if description:
        return description
    return ""


def _avg_pace(activity: Dict[str, Any]) -> Optional[str]:
    distance_m = activity.get("distance") or 0
    moving_time = activity.get("moving_time") or 0
    if distance_m <= 0 or moving_time <= 0:
        return None
    minutes_per_km = (moving_time / 60) / (distance_m / 1000.0)
    return _format_pace(minutes_per_km)


def _gear_name(
    client: StravaClient, gear_id: Optional[str], cache: Dict[str, str]
) -> Optional[str]:
    if not gear_id:
        return None
    if gear_id in cache:
        return cache[gear_id]
    gear = client.get_gear(gear_id)
    name = gear.get("name")
    if name:
        cache[gear_id] = name
        save_gear_cache(cache)
        return name
    return None


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def map_activity_to_run(
    activity: Dict[str, Any], client: StravaClient, gear_cache: Dict[str, str]
) -> Dict[str, Any]:
    distance_km = (activity.get("distance") or 0) / 1000.0
    moving_time = activity.get("moving_time") or 0
    duration_min = moving_time / 60.0
    return {
        "date": _activity_date(activity).isoformat(),
        "type": _run_type(activity),
        "distance_km": _round_1(distance_km),
        "duration_min": _round_1(duration_min),
        "avg_pace": _avg_pace(activity),
        "avg_hr": _as_int(activity.get("average_heartrate")),
        "max_hr": _as_int(activity.get("max_heartrate")),
        "training_load": _as_int(activity.get("suffer_score")),
        "shoes": _gear_name(client, activity.get("gear_id"), gear_cache),
        "rpe": None,
        "notes": _activity_notes(activity, "Run"),
        "splits": [],
    }


def map_activity_to_ride(activity: Dict[str, Any]) -> Dict[str, Any]:
    moving_time = activity.get("moving_time") or 0
    duration_min = moving_time / 60.0
    return {
        "date": _activity_date(activity).isoformat(),
        "type": _ride_type(activity),
        "duration_min": _round_1(duration_min),
        "avg_power": _as_int(activity.get("average_watts")),
        "norm_power": _as_int(activity.get("weighted_average_watts")),
        "avg_hr": _as_int(activity.get("average_heartrate")),
        "training_load": _as_int(activity.get("suffer_score")),
        "rpe": None,
        "notes": _activity_notes(activity, "Ride"),
    }


def export_weekly_json(
    activities: List[Dict[str, Any]],
    client: StravaClient,
    week_start: str,
    week_end: str,
    include_private: bool,
    include_commute: bool,
) -> Tuple[Dict[str, Any], Dict[str, int]]:
    runs: List[Dict[str, Any]] = []
    rides: List[Dict[str, Any]] = []
    skipped: Dict[str, int] = {}
    gear_cache = load_gear_cache()

    for activity in activities:
        if not include_private and activity.get("private"):
            skipped["private"] = skipped.get("private", 0) + 1
            continue
        if not include_commute and activity.get("commute"):
            skipped["commute"] = skipped.get("commute", 0) + 1
            continue

        activity_type = activity.get("type")
        if activity_type in {"Run", "VirtualRun"}:
            run = map_activity_to_run(activity, client, gear_cache)
            if activity_type in {"Run", "VirtualRun"}:
                activity_id = activity.get("id")
                if activity_id is not None:
                    detail = client.get_activity_detail(activity_id)
                    run["notes"] = _activity_description(detail)
                else:
                    run["notes"] = ""
            runs.append(run)
        elif activity_type in {"Ride", "VirtualRide"}:
            ride = map_activity_to_ride(activity)
            if activity_type in {"Ride", "VirtualRide"}:
                activity_id = activity.get("id")
                if activity_id is not None:
                    detail = client.get_activity_detail(activity_id)
                    ride["notes"] = _activity_description(detail)
                else:
                    ride["notes"] = ""
            rides.append(ride)
        else:
            skipped[activity_type or "unknown"] = skipped.get(activity_type or "unknown", 0) + 1

    runs.sort(key=lambda x: x["date"])
    rides.sort(key=lambda x: x["date"])

    payload = {
        "week_start": week_start,
        "week_end": week_end,
        "body_weight": None,
        "notes": "",
        "runs": runs,
        "rides": rides,
        "strength": [],
        "yoga": [],
        "other": [],
    }
    return payload, skipped


def write_weekly_json(payload: Dict[str, Any], out_dir: Path, week_start: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"weekly_{week_start}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return out_path
