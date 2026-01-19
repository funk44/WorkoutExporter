# Strava Weekly Export

- Export weekly Strava Run/Ride activities to JSON for training logs.
- Upload planned Run workouts to Intervals.icu from a simple JSON format.
- Archive uploaded plans for later comparison with executed weeks.

## Requirements

- Python 3.11+
- Internet access for Strava and Intervals.icu APIs

## Install

Editable install:

```bash
pip install -e .
```

Or with pipx:

```bash
pipx install -e .
```

## Quick start

1) Create a Strava API app: https://www.strava.com/settings/api  
2) Set the callback URL to `http://localhost:8080/callback`  
3) Set env vars:

```bash
export STRAVA_CLIENT_ID="your_client_id"
export STRAVA_CLIENT_SECRET="your_client_secret"
```

4) Run auth once (interactive):

```bash
strava-weekly-export --auth
```

5) Export last week:

```bash
strava-weekly-export --last-week
```

Output JSON is written to `./out/weekly_YYYY-MM-DD.json`.

## Commands

Export weekly activities:

```bash
strava-weekly-export --last-week
strava-weekly-export --this-week
strava-weekly-export --week-start 2024-07-01 --week-end 2024-07-07
strava-weekly-export --last-week --intervals
```

Options:

- `--week-start` / `--week-end` (YYYY-MM-DD)
- `--this-week` (Monday..Sunday in Australia/Melbourne)
- `--last-week` (Monday..Sunday in Australia/Melbourne)
- `--out` (output dir, default `./out`)
- `--include-private` / `--no-include-private`
- `--include-commute` / `--no-include-commute`
- `--auth` (run interactive Strava OAuth)
- `--dry-run` (print first mapped activity)
- `--intervals` (export completed activities from Intervals.icu instead of Strava)
- `--debug`

Upload planned workouts to Intervals.icu:

```bash
strava-weekly-export intervals-push --planned ./planned_workouts.json
```

Options:

- `--planned` (path to planned workouts JSON)
- `--from` / `--to` (YYYY-MM-DD date filters)
- `--dry-run` (print rendered workouts)
- `--validate-only` (validate and render, no upload)
- `--adhoc` (disable plan archiving)
- `--debug`

Notes:

- Only Run workouts are uploaded to Intervals.icu; other sports are skipped.
- Dry run and validate-only do not call the API.

## Configuration

Environment variables:

| Name | Required | Description | Example |
| --- | --- | --- | --- |
| `STRAVA_CLIENT_ID` | Yes | Strava API app client ID | `12345` |
| `STRAVA_CLIENT_SECRET` | Yes | Strava API app client secret | `abc123` |
| `INTERVALS_API_KEY` | For `intervals-push` and `--intervals` export | Intervals.icu API key (HTTP Basic auth) | `your_api_key` |
| `INTERVALS_ATHLETE_ID` | No | Intervals.icu athlete id (default `0`) | `0` |
| `LOCAL_TIMEZONE` | No | Timezone for week boundaries (IANA tz, default `Australia/Melbourne`) | `Europe/London` |
| `PLANS_DIR` | No | Plan archive directory (default `./plans`) | `./plans` |

### Intervals.icu: Get your Athlete ID and API Key

- Log into Intervals.icu and open Settings.
- Find your Athlete ID (this is the numeric id for your athlete profile) and copy it.
- Find your API key and copy it.
- Set the environment variables used by this tool:
  - `INTERVALS_API_KEY` (required for uploads and `--intervals` export)
  - `INTERVALS_ATHLETE_ID` (optional, defaults to `0`)

Example:

```bash
export INTERVALS_API_KEY="your_intervals_api_key"
export INTERVALS_ATHLETE_ID="0"
strava-weekly-export intervals-push --planned ./planned_workouts.json
```

## Files and storage

- Strava tokens: `./secrets/strava_tokens.json`
- Gear cache: `./secrets/gear_cache.json`
- Weekly exports: `./out/weekly_YYYY-MM-DD.json`
- Plan archives: `./plans/plan_YYYY-MM-DD.json` (overwritten per week)

Do not commit `./secrets`, `.env`, or generated output folders.

## Export details

- Activities exported: Runs and Rides only (Strava activity types `Run`/`VirtualRun` and `Ride`/`VirtualRide`).
- Notes field: populated from the Strava activity description when available (Run/Ride/VirtualRun/VirtualRide); otherwise empty string.
- Week boundaries are Monday..Sunday, computed in `LOCAL_TIMEZONE` (default `Australia/Melbourne`).
- If `LOCAL_TIMEZONE` is invalid, the tool prints a warning and falls back to the default.
- Exported file naming uses the local Monday date.
- Intervals.icu export uses the same schema; shoes may be null and Intervals-only metrics appear under `extra`.

Example timezone override:

```bash
export LOCAL_TIMEZONE="Europe/London"
strava-weekly-export --last-week
```

## Planned workouts JSON (Intervals.icu)

Top level is a list of workouts (or an object with a `workouts` list). Each workout must include:

- `date` (YYYY-MM-DD)
- `name` (non-empty string)
- `sport` (string, only `Run` is uploaded)
- Either `time` (HH:MM or HH:MM:SS) or `all_day: true`
- Either `trainings` (list) or `sections` (non-empty list)

Training step formats:

- Simple step: `{ "duration": 90, "pace": 80, "description": "Easy jog" }`
- Repeat block: `{ "repeat": { "count": 8, "trainings": [ ... ] } }`

`duration` can be an integer seconds or a string with `m`, `km`, or `s` (for example `"20m"` or `"400m"`).  
`pace` is an integer percentage from 1 to 150.

If `all_day: true` is used, uploads use a fixed `start_date_local` of `12:00:00` on that date.

Intervals.icu uploads use an `external_id` derived from workout date and name. Renaming a workout changes the `external_id` and can create a duplicate calendar entry. If you need to rename, delete the old event in Intervals.icu first.

### How pace percentages work

- Each training step `pace` is an integer percent (for example `80`, `95`, `112`).
- These percentages are relative to your Threshold pace in Intervals.icu.
- Set it in Intervals.icu: Settings → Sport Settings → Run → Threshold pace.

Example (threshold pace = 4:30/km):

- 80% ≈ easy pace
- 100% ≈ threshold pace
- 112% ≈ faster-than-threshold strides

Intervals.icu uses these settings to translate your plan into a structured workout that Garmin can display step-by-step.

Common mistakes:

- Using the wrong Athlete ID
- Leaving Threshold pace unset
- Pace percentages looking wrong because Threshold pace is outdated

Minimal valid example:

```json
[
  {
    "date": "2024-07-01",
    "time": "06:00",
    "sport": "Run",
    "name": "Strides",
    "sections": [
      {
        "name": "Warmup",
        "trainings": [
          { "duration": "20m", "pace": 80, "description": "" }
        ]
      },
      {
        "name": "Main set",
        "trainings": [
          {
            "repeat": {
              "count": 8,
              "trainings": [
                { "duration": "20s", "pace": 112, "description": "Stride fast" },
                { "duration": 90, "pace": 68, "description": "Easy jog" }
              ]
            }
          }
        ]
      },
      {
        "name": "Cooldown",
        "trainings": [
          { "duration": "10m", "pace": 80, "description": "" }
        ]
      }
    ]
  }
]
```

## Troubleshooting

- Missing env vars: ensure `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` are set.
- Auth failures: re-run `strava-weekly-export --auth` and confirm the callback URL.
- Rate limiting: the client retries automatically, but large weeks may take longer.
- Week boundary confusion: exports are Monday..Sunday in `Australia/Melbourne`.
- Intervals.icu upload fails: confirm `INTERVALS_API_KEY` and `INTERVALS_ATHLETE_ID`.
- Garmin sync: ensure Intervals.icu <-> Garmin integration is enabled in Intervals.icu.

## Security notes

- Never commit tokens or API keys.
- Keep `./secrets` and `.env` local only.
- Treat archived plans and exports as private training data.
