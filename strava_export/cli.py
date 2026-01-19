import argparse
import json
import os
import re
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dateutil import parser

from .auth import ensure_valid_tokens, run_interactive_auth
from .config import load_env, load_intervals_env, load_local_timezone, load_tokens
from .export_week import export_weekly_json, write_weekly_json
from .export_week_intervals import export_weekly_json_from_intervals
from .intervals_client import IntervalsClient
from .plan_archive import archive_plan
from .strava_client import StravaClient
from .workout_render import render_intervals_workout_text, validate_planned_workout


LOCAL_TZ = load_local_timezone()


def _parse_date(value: str) -> datetime.date:
    return parser.isoparse(value).date()


def _week_bounds_from_dates(start_date: datetime.date, end_date: datetime.date) -> Tuple[int, int]:
    start_dt = datetime.combine(start_date, time.min, tzinfo=LOCAL_TZ)
    end_dt = datetime.combine(end_date, time.max, tzinfo=LOCAL_TZ)
    return int(start_dt.timestamp()), int(end_dt.timestamp())


def _compute_week_range(mode: str) -> Tuple[str, str]:
    now = datetime.now(tz=LOCAL_TZ).date()
    if mode == "this":
        start = now - timedelta(days=now.weekday())
    else:
        start = now - timedelta(days=now.weekday() + 7)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def _validate_week_args(args: argparse.Namespace) -> Tuple[str, str]:
    if args.this_week and args.last_week:
        raise RuntimeError("Use only one of --this-week or --last-week.")
    if args.this_week:
        return _compute_week_range("this")
    if args.last_week:
        return _compute_week_range("last")
    if not args.week_start or not args.week_end:
        raise RuntimeError("Provide --week-start and --week-end, or use --this-week/--last-week.")
    start = _parse_date(args.week_start).isoformat()
    end = _parse_date(args.week_end).isoformat()
    return start, end


def _summary(payload: Dict[str, Any], skipped: Dict[str, int]) -> str:
    run_km = sum(r["distance_km"] for r in payload["runs"])
    ride_min = sum(r["duration_min"] for r in payload["rides"])
    skipped_parts = [f"{k}={v}" for k, v in sorted(skipped.items())]
    skipped_str = ", ".join(skipped_parts) if skipped_parts else "none"
    return (
        f"Runs: {len(payload['runs'])}, Rides: {len(payload['rides'])}, "
        f"Run km: {run_km:.1f}, Ride min: {ride_min:.1f}, Skipped: {skipped_str}"
    )


def _build_export_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export weekly activities to JSON.")
    parser.add_argument("--week-start", help="YYYY-MM-DD")
    parser.add_argument("--week-end", help="YYYY-MM-DD")
    parser.add_argument("--this-week", action="store_true", help="Use Monday..Sunday this week")
    parser.add_argument("--last-week", action="store_true", help="Use Monday..Sunday last week")
    parser.add_argument("--out", default="./out", help="Output directory")
    parser.add_argument(
        "--include-private",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include private activities",
    )
    parser.add_argument(
        "--include-commute",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include commute activities",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--auth", action="store_true", help="Run interactive auth flow")
    parser.add_argument("--dry-run", action="store_true", help="Print first mapped activity")
    parser.add_argument(
        "--intervals",
        action="store_true",
        help="Export completed activities from Intervals.icu instead of Strava",
    )
    return parser


def _build_intervals_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload planned run workouts to Intervals.icu."
    )
    parser.add_argument(
        "--planned",
        required=True,
        help="Path to planned workouts JSON (date + time or all_day required)",
    )
    parser.add_argument("--from", dest="from_date", help="YYYY-MM-DD start filter (date only)")
    parser.add_argument("--to", dest="to_date", help="YYYY-MM-DD end filter (date only)")
    parser.add_argument("--dry-run", action="store_true", help="Print rendered workouts")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate and render workouts without uploading",
    )
    parser.add_argument("--adhoc", action="store_true", help="Disable plan archiving")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    return parser


def _load_planned_workouts(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("workouts"), list):
        return data["workouts"]
    raise RuntimeError("Planned workouts JSON must be a list or {\"workouts\": [...]} object.")


def _require_time(value: Optional[str]) -> str:
    if not value:
        raise RuntimeError("Missing required field: time (HH:MM or HH:MM:SS)")
    parts = value.strip().split(":")
    if len(parts) not in (2, 3):
        raise RuntimeError(f"Invalid time format: {value}")
    try:
        hh = int(parts[0])
        mm = int(parts[1])
        ss = int(parts[2]) if len(parts) == 3 else 0
    except ValueError as exc:
        raise RuntimeError(f"Invalid time format: {value}") from exc
    if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
        raise RuntimeError(f"Invalid time value: {value}")
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-") or "workout"


def _workout_context(index: int, workout: Dict[str, Any]) -> str:
    name = workout.get("name") or "<missing name>"
    date = workout.get("date") or "<missing date>"
    return f"workout[{index}] name={name} date={date}"


def _validate_workout_entry(index: int, workout: Dict[str, Any]) -> None:
    if not isinstance(workout, dict):
        raise RuntimeError(f"workout[{index}] must be an object")
    context = _workout_context(index, workout)
    date = workout.get("date")
    if not date:
        raise RuntimeError(f"{context} missing required field: date (YYYY-MM-DD)")
    try:
        _parse_date(date)
    except Exception as exc:
        raise RuntimeError(f"{context} invalid date format (YYYY-MM-DD)") from exc
    name = workout.get("name")
    if not isinstance(name, str) or not name.strip():
        raise RuntimeError(f"{context} invalid name (non-empty string required)")
    sport = workout.get("sport")
    if not isinstance(sport, str) or not sport.strip():
        raise RuntimeError(f"{context} invalid sport (non-empty string required)")
    time_str = workout.get("time")
    all_day = workout.get("all_day")
    if time_str is None and not all_day:
        raise RuntimeError(f"{context} missing time (HH:MM or HH:MM:SS) or all_day: true")
    if time_str is not None:
        try:
            _require_time(time_str)
        except Exception as exc:
            raise RuntimeError(f"{context} invalid time (HH:MM or HH:MM:SS)") from exc
    try:
        validate_planned_workout(workout)
    except Exception as exc:
        raise RuntimeError(f"{context} trainings invalid: {exc}") from exc


def _intervals_command(args: argparse.Namespace) -> int:
    workouts = _load_planned_workouts(Path(args.planned))
    from_date = _parse_date(args.from_date).isoformat() if args.from_date else None
    to_date = _parse_date(args.to_date).isoformat() if args.to_date else None

    events: List[Dict[str, Any]] = []
    selected_workouts: List[Dict[str, Any]] = []
    skipped = 0
    for idx, workout in enumerate(workouts):
        _validate_workout_entry(idx, workout)
        workout_date = workout["date"]
        if from_date and workout_date < from_date:
            continue
        if to_date and workout_date > to_date:
            continue
        sport = workout["sport"]
        if sport != "Run":
            skipped += 1
            continue
        name = workout["name"]
        if workout.get("time") is not None:
            time_str = _require_time(workout["time"])
            start_date_local = f"{workout_date}T{time_str}"
        else:
            start_date_local = f"{workout_date}T12:00:00"
        description = render_intervals_workout_text(workout)
        external_id = f"planned-run-{workout_date}-{_slugify(name)}"
        selected_workouts.append(workout)
        events.append(
            {
                "category": "WORKOUT",
                "start_date_local": start_date_local,
                "type": "Run",
                "name": name,
                "description": description,
                "external_id": external_id,
            }
        )

    events.sort(key=lambda e: e["start_date_local"])

    if not events:
        print("Warning: no workouts selected for upload.")

    if args.dry_run or args.validate_only:
        for event in events:
            print(f"{event['start_date_local']} {event['name']}")
            print(event["description"])
            print("")
        if args.validate_only:
            print(f"Validation complete. Events: {len(events)}, Skipped non-run: {skipped}")
        else:
            print(f"Dry run complete. Events: {len(events)}, Skipped non-run: {skipped}")
        return 0

    intervals_env = load_intervals_env()
    client = IntervalsClient(
        intervals_env.api_key, athlete_id=intervals_env.athlete_id, debug=args.debug
    )
    try:
        client.upsert_events(events)
    finally:
        client.close()
    print(f"Uploaded {len(events)} workouts. Skipped non-run: {skipped}")
    if not args.adhoc:
        plans_dir = Path(os.getenv("PLANS_DIR", "./plans"))
        archive_path = archive_plan(selected_workouts, args.planned, plans_dir)
        if archive_path:
            print(f"Archived planned week to {archive_path}")
    return 0


def _export_command(args: argparse.Namespace) -> int:
    try:
        if args.intervals:
            if args.auth:
                raise RuntimeError("--auth is only valid for Strava exports.")
            week_start, week_end = _validate_week_args(args)
            intervals_env = load_intervals_env()
            client = IntervalsClient(
                intervals_env.api_key, athlete_id=intervals_env.athlete_id, debug=args.debug
            )
            try:
                activities = client.list_activities(oldest=week_start, newest=week_end)
                payload, skipped = export_weekly_json_from_intervals(
                    activities, week_start, week_end
                )
            finally:
                client.close()
        else:
            env = load_env()
            if args.auth:
                run_interactive_auth(env)
                print("Auth completed and tokens saved.")
                return 0
            week_start, week_end = _validate_week_args(args)
            start_date = _parse_date(week_start)
            end_date = _parse_date(week_end)
            after_epoch, before_epoch = _week_bounds_from_dates(start_date, end_date)

            tokens = ensure_valid_tokens(env, load_tokens())
            access_token = tokens.get("access_token")
            if not access_token:
                raise RuntimeError("Access token missing after refresh. Run auth again.")

            client = StravaClient(access_token, debug=args.debug)
            try:
                activities = client.list_activities(after_epoch, before_epoch)
                payload, skipped = export_weekly_json(
                    activities,
                    client,
                    week_start,
                    week_end,
                    include_private=args.include_private,
                    include_commute=args.include_commute,
                )
            finally:
                client.close()

        if args.dry_run:
            sample = None
            if payload["runs"]:
                sample = payload["runs"][0]
            elif payload["rides"]:
                sample = payload["rides"][0]
            if sample:
                print(json.dumps(sample, indent=2))
            else:
                print("No activities to sample.")
            print(_summary(payload, skipped))
            return 0

        out_path = write_weekly_json(payload, Path(args.out), week_start)
        print(f"Wrote {out_path}")
        print(_summary(payload, skipped))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "intervals-push":
        parser = _build_intervals_parser()
        args = parser.parse_args(sys.argv[2:])
        try:
            return _intervals_command(args)
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    parser = _build_export_parser()
    args = parser.parse_args()
    return _export_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
