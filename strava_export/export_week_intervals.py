from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from dateutil import parser


def _round_1(value: float) -> float:
    return round(value + 1e-9, 1)


def _format_pace(minutes_per_km: float) -> str:
    total_seconds = int(round(minutes_per_km * 60))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _activity_date(activity: Dict[str, Any]) -> Optional[date]:
    start_local = activity.get("start_date_local") or activity.get("start_date")
    if not start_local:
        return None
    try:
        return parser.isoparse(start_local).date()
    except Exception:
        return None


def _first_value(activity: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for key in keys:
        value = activity.get(key)
        if value is not None:
            return value
    return None


def _raw_distance_km(activity: Dict[str, Any]) -> float:
    raw = _first_value(activity, ["distance", "distance_km", "dist"])
    if raw is None:
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value <= 0:
        return 0.0
    if value > 1000:
        return value / 1000.0
    return value


def _raw_duration_min(activity: Dict[str, Any]) -> float:
    raw = _first_value(activity, ["moving_time", "duration", "elapsed_time"])
    if raw is None:
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value <= 0:
        return 0.0
    return value / 60.0


def _avg_pace(activity: Dict[str, Any]) -> Optional[str]:
    distance_km = _raw_distance_km(activity)
    duration_min = _raw_duration_min(activity)
    if distance_km <= 0 or duration_min <= 0:
        return None
    return _format_pace(duration_min / distance_km)


def _run_type(activity: Dict[str, Any]) -> str:
    name = (activity.get("name") or "").lower()
    if "race" in name:
        return "race"
    if "long" in name:
        return "long"
    if "interval" in name or "vo2" in name:
        return "intervals"
    if "tempo" in name:
        return "tempo"
    if "progression" in name:
        return "progression"
    if "recovery" in name:
        return "recovery"
    if "easy" in name:
        return "easy"
    return "unknown"


def _ride_type(activity: Dict[str, Any]) -> str:
    name = (activity.get("name") or "").lower()
    if activity.get("trainer"):
        return "zwift_tempo" if "zwift" in name else "unknown"
    if activity.get("commute"):
        return "recovery"
    if "race" in name:
        return "race"
    return "outdoor_endurance"


def _is_ride(activity_type: Optional[str]) -> bool:
    if not activity_type:
        return False
    return activity_type in {
        "Ride",
        "Virtual Ride",
        "VirtualRide",
        "E-Bike Ride",
        "Mountain Bike Ride",
        "Gravel Ride",
    }


def _activity_notes(activity: Dict[str, Any]) -> str:
    return activity.get("notes") or activity.get("description") or ""


def _extra_fields(activity: Dict[str, Any]) -> Dict[str, Any]:
    extra: Dict[str, Any] = {}
    for key in (
        "id",
        "name",
        "calories",
        "elevation_gain",
        "avg_cadence",
        "avg_speed",
        "max_speed",
        "work",
        "icu_intensity",
        "icu_training_load",
        "training_load",
        "ctl",
        "atl",
        "tsb",
    ):
        value = activity.get(key)
        if value is not None:
            extra[key] = value
    return extra


def export_weekly_json_from_intervals(
    activities: List[Dict[str, Any]], week_start: str, week_end: str
) -> Tuple[Dict[str, Any], Dict[str, int]]:
    runs: List[Dict[str, Any]] = []
    rides: List[Dict[str, Any]] = []
    skipped: Dict[str, int] = {}

    for activity in activities:
        activity_date = _activity_date(activity)
        if activity_date is None:
            skipped["missing_date"] = skipped.get("missing_date", 0) + 1
            continue

        activity_type = activity.get("type")
        if activity_type == "Run":
            distance_km_raw = _raw_distance_km(activity)
            duration_min_raw = _raw_duration_min(activity)
            run = {
                "date": activity_date.isoformat(),
                "type": _run_type(activity),
                "distance_km": _round_1(distance_km_raw),
                "duration_min": _round_1(duration_min_raw),
                "avg_pace": _avg_pace(activity),
                "avg_hr": _as_int(
                    _first_value(activity, ["avg_hr", "average_hr", "average_heartrate"])
                ),
                "max_hr": _as_int(
                    _first_value(activity, ["max_hr", "max_heartrate"])
                ),
                "training_load": _as_int(
                    _first_value(activity, ["icu_training_load", "training_load"])
                ),
                "shoes": None,
                "rpe": _as_int(activity.get("feel")),
                "notes": _activity_notes(activity),
                "splits": [],
                "extra": _extra_fields(activity),
            }
            runs.append(run)
        elif _is_ride(activity_type):
            duration_min_raw = _raw_duration_min(activity)
            ride = {
                "date": activity_date.isoformat(),
                "type": _ride_type(activity),
                "duration_min": _round_1(duration_min_raw),
                "avg_power": _as_int(
                    _first_value(activity, ["avg_power", "average_power", "avg_watts"])
                ),
                "norm_power": _as_int(
                    _first_value(activity, ["norm_power", "normalized_power"])
                ),
                "avg_hr": _as_int(
                    _first_value(activity, ["avg_hr", "average_hr", "average_heartrate"])
                ),
                "training_load": _as_int(
                    _first_value(activity, ["icu_training_load", "training_load"])
                ),
                "rpe": _as_int(activity.get("feel")),
                "notes": _activity_notes(activity),
                "extra": _extra_fields(activity),
            }
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
