# Strava Weekly Export & Intervals.icu Planner

A CLI tool for exporting weekly training data from Strava, using ChatGPT to generate structured training plans, and uploading those plans directly to Intervals.icu for execution and sync to Garmin (or other platforms).

This project is designed to support a **human-in-the-loop planning workflow**:

- Export what you actually did last week  
- Ask ChatGPT to plan next week using real data  
- Upload the structured plan directly into Intervals.icu  
- Execute, track, repeat  

It deliberately avoids “AI auto-planning in the background” — you remain in control of training decisions, load, and progression.

---

## Quickstart

This section gets you from zero to a working export + upload as quickly as possible.

### 1. Install

Clone the repo and install dependencies:

```bash
git clone https://github.com/funk44/WorkoutExporter.git
cd WorkoutExporter
pip install -e .
```

---

### 2. Set environment variables

#### Required

These are mandatory for the tool to function.

The commands depend on your operating system and shell.

#### macOS / Linux (bash, zsh)

```bash
export STRAVA_CLIENT_ID=...
export STRAVA_CLIENT_SECRET=...
export INTERVALS_API_KEY=...
```

Where:

- `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET`  
  → From https://www.strava.com/settings/api  

- `INTERVALS_API_KEY`  
  → From Intervals.icu → Settings → API  

#### Optional

```bash
export LOCAL_TIMEZONE=Australia/Melbourne
```

Notes:

- Timezone is used to define week boundaries correctly  
- If unset, the system timezone is used  

---

### 3. First run (Strava OAuth)

On first run, the CLI will:

- Open a browser window for Strava OAuth  
- Ask you to authorise the app  
- Persist tokens under `./secrets`  

Sanity check:

```bash
strava-weekly-export --last-week
```

If this succeeds, authentication is complete.

---

### 4. Verify Intervals.icu connectivity

Dry-run validation:

```bash
strava-weekly-export intervals-push --planned ./planned_workouts.json --validate-only
```

If validation runs without API errors, Intervals authentication is working.

---

## What this does

This repo provides two main capabilities:

### 1. Weekly Strava export (actual training)

- Fetches last week’s activities from Strava  
- Normalises them into a clean weekly JSON summary  
- Suitable for pasting directly into ChatGPT  

Used for:
- Training review  
- Fatigue / load awareness  
- Data-driven planning  

### 2. Planned workout upload to Intervals.icu

- Takes a JSON file describing next week’s planned runs  
- Validates it against the Intervals.icu API schema  
- Uploads it as planned workouts  
- Archives the plan locally for comparison later  

Used for:
- Structured run planning  
- Garmin / Intervals calendar sync  
- Long-term consistency  

Only **Run** workouts are uploaded by design. Other sports can be planned conceptually but are ignored by the uploader.

---

## Intended workflow (weekly loop with ChatGPT)

This is the core design pattern of the project.

### Step 1 — Export last week’s actual training

```bash
strava-weekly-export --last-week
```

This produces:

- `./out/weekly_YYYY-MM-DD.json` (named by the Monday of that week)

This file contains:
- Each activity (date, distance, duration, HR, pace, etc.)
- Suitable for direct analysis or planning input  

---

### Step 2 — Paste export into ChatGPT

Open ChatGPT and paste:

- The exported weekly JSON  
- An “athlete profile” prompt (template provided below)  

Ask ChatGPT to:
- Review last week  
- Propose next week’s structure  
- Output a **planned workouts JSON** matching this repo’s schema  

---

## One-time setup: committing your athlete profile to ChatGPT memory (recommended)

For best results, it is strongly recommended that you **commit your long-term training profile to ChatGPT memory once**, so you do not need to repeat it every week.

This includes things like:

- Long-term goals (e.g. target races, time goals, seasons)
- Injury history and risk areas
- Preferred training structure and days
- Weekly volume ranges
- Strength / cross-training habits
- Heat tolerance and environment constraints
- Coaching philosophy (conservative vs aggressive, injury-averse, etc.)

After providing this context once, explicitly ask ChatGPT:

> “Please save this athlete profile to memory so we can reuse it for future planning.”

From that point on:

- Weekly planning prompts only need last week’s export  
- You do **not** need to restate goals and constraints each time  
- Plans become progressively more consistent and personalised  

If you ever change goals, race targets, or constraints, simply update them and ask ChatGPT to overwrite the stored profile.

This keeps weekly planning lightweight while preserving long-term continuity.

---

### Step 3 — Save ChatGPT’s output locally

Save ChatGPT’s planned output as:

- `./planned_workouts.json`

This must follow the planned-workouts schema (see below).

---

### Step 4 — Validate locally (strongly recommended)

Before uploading anything:

```bash
strava-weekly-export intervals-push --planned ./planned_workouts.json --validate-only
```

This:
- Parses and validates the structure  
- Prints rendered workouts  
- Prevents API failures and broken uploads  

---

### Step 5 — Upload to Intervals.icu

```bash
strava-weekly-export intervals-push --planned ./planned_workouts.json
```

On success:
- Workouts appear in Intervals.icu  
- They sync to Garmin automatically (if connected)  
- The plan is archived locally to `./plans/plan_YYYY-MM-DD.json`  

---

### Step 6 — Compare plan vs actual (optional but powerful)

Next week you can compare:

- `./plans/plan_YYYY-MM-DD.json` (what you planned)  
- `./out/weekly_YYYY-MM-DD.json` (what you actually did)  

This enables:
- Adherence tracking  
- Load management  
- Prompt refinement over time  

---

## Boilerplate ChatGPT prompt (copy / paste)

Use this when generating next week’s plan (or for your initial memory setup).  
Replace the bracketed values with your own details.

```text
You are helping me plan next week of training and produce a JSON file that can be uploaded to Intervals.icu using my CLI tool.

CONTEXT / ATHLETE PROFILE
- Primary goal: [e.g., build half marathon fitness / prep for race on YYYY-MM-DD]
- Current weekly volume: [e.g., 40–55 km running/week]
- Long run status: [e.g., comfortable at 16 km; building gradually]
- Injury / risk flags: [e.g., calf history; avoid spikes; no back-to-back hard days]
- Heat / environment: [e.g., often running in 22–30°C mornings]
- Available days & constraints:
  - [e.g., run Tue/Wed/Fri/Sat/Sun]
  - [e.g., travel Thu, no training]
  - [e.g., gym access yes/no]
- Preferences:
  - Structured runs, not vague “easy / moderate”
  - Keep easy days genuinely easy
  - Include strides / light anaerobic touches if appropriate
  - No hero workouts or sudden jumps
- Intervals.icu settings:
  - Run threshold pace: [e.g., 4:30/km]
  - Pace % conventions (unless I say otherwise):
    - Easy: 80–85%
    - Recovery jog: 65–70%
    - Strides: ~100–112%
    - Tempo / threshold / intervals: choose sensible values and explain them

INPUT DATA (LAST WEEK ACTUALS)
I will paste a JSON export of last week’s completed training below. Use it to:
- infer fatigue and load
- keep progression conservative
- avoid repeating hard days back-to-back
- maintain sensible weekly structure

TASK
1) Propose a next-week plan (brief explanation first: structure + intent).
2) Output ONLY the planned-workouts JSON matching this schema:
   - A list of workout objects
   - Each workout has: date, all_day OR time, sport, name, sections
   - sections contain trainings
   - trainings are either:
     - steps: {duration, pace, description}
     - or repeat blocks: {repeat:{count, trainings:[...]}}
3) Only include Run workouts in the JSON.
4) Make reasonable assumptions if needed and state them clearly.

NOW HERE IS LAST WEEK’S EXPORT JSON:
[paste weekly_YYYY-MM-DD.json here]
```

---

## Planned workout JSON schema (Intervals.icu)

Planned uploads must follow this structure exactly:

```json
[
  {
    "date": "2026-01-21",
    "time": "06:30",
    "sport": "Run",
    "name": "Progression Run",
    "sections": [
      {
        "name": "Main Set",
        "trainings": [
          {
            "duration": "10m",
            "pace": 0.85,
            "description": "Easy warm-up"
          },
          {
            "repeat": {
              "count": 4,
              "trainings": [
                {
                  "duration": "3m",
                  "pace": 1.00,
                  "description": "Threshold"
                },
                {
                  "duration": "2m",
                  "pace": 0.70,
                  "description": "Recovery jog"
                }
              ]
            }
          }
        ]
      }
    ]
  }
]
```

### Notes

- `pace` is a fraction of Intervals.icu threshold pace (e.g., `0.85 = 85%`)  
- Durations use Intervals format: `"5m"`, `"30s"`, `"1h"`  
- Only workouts with `"sport": "Run"` are uploaded  
- Sections and repeats are fully supported  

---

## CLI overview

The CLI provides two primary modes:

- **Weekly Strava export** (actual training history)  
- **Intervals.icu planned workout upload** (future training plans)  

It also includes helpers for validation, archiving, ad-hoc uploads, and flexible date ranges.

---

### Export last week (most common)

Export the previous Monday–Sunday training week from Strava:

```bash
strava-weekly-export --last-week
```

Writes:

- `./out/weekly_YYYY-MM-DD.json`

Where `YYYY-MM-DD` is the Monday of that week.

---

### Export a specific date range

Export any arbitrary date range:

```bash
strava-weekly-export --from 2026-01-01 --to 2026-01-07
```

Notes:

- Dates are inclusive  
- Week boundaries are derived from local timezone  
- Useful for:
  - Partial weeks  
  - Travel weeks  
  - Backfills  
  - Debugging  

---

### Ad-hoc exports (one-off or debugging)

Export a single day or a small custom window for inspection or debugging:

```bash
strava-weekly-export --from 2026-01-21 --to 2026-01-21
```

This is useful for:

- Inspecting a specific workout  
- Debugging pace / HR parsing  
- Testing schema changes  
- Reviewing race days or key sessions  

Notes:

- Output format is identical to weekly exports  
- Dates are inclusive  
- No week alignment is enforced in this mode  

---

### Upload planned workouts to Intervals.icu (full week)

Upload a planned week JSON file:

```bash
strava-weekly-export intervals-push --planned ./planned_workouts.json
```

This will:

- Validate the JSON structure  
- Upload all Run workouts  
- Archive the plan to `./plans/plan_YYYY-MM-DD.json`  

---

### Validate a planned week (no upload)

Strongly recommended before every upload:

```bash
strava-weekly-export intervals-push --planned ./planned_workouts.json --validate-only
```

This:

- Parses and validates the full schema  
- Renders workouts to the console  
- Does **not** call the Intervals API  
- Prevents malformed uploads and silent failures  

---

### Archive-only mode (no upload)

Archive a plan without uploading it yet:

```bash
strava-weekly-export intervals-push --planned ./planned_workouts.json --archive-only
```

This:

- Validates the file  
- Writes it to `./plans/`  
- Skips API calls  

Useful for:

- Versioning plans  
- Reviewing later  
- Comparing multiple drafts  

---

### Ad-hoc upload mode (partial or single-workout uploads)

Upload one or more workouts without requiring a full weekly plan wrapper:

```bash
strava-weekly-export intervals-push --planned ./planned_workouts.json --adhoc
```

This mode is intended for:

- Uploading a **single workout**  
- Uploading only part of a week  
- Testing new workout structures  
- Making small corrections without regenerating a full plan  

In this mode:

- The input file may contain:
  - A single workout object, or  
  - A list of workout objects  
- No `week_start` or metadata wrapper is required  
- Workouts are uploaded exactly as provided  

Important semantics:

- **No archiving is performed in `--adhoc` mode**  
- This mode is intentionally non-persistent  
- It does not write to `./plans/`  

Notes:

- Validation still runs normally  
- Duplicate date / identifier rules still apply in Intervals.icu  

Tip: `--adhoc` is ideal for adding or fixing individual workouts without regenerating, archiving, or re-uploading an entire week.

---

### Re-upload or overwrite an existing planned week

If a week has already been uploaded and you want to replace it:

- Delete the planned workouts in Intervals.icu first, or  
- Change the workout names / identifiers in the JSON  

Then re-run:

```bash
strava-weekly-export intervals-push --planned ./planned_workouts.json
```

Intervals requires unique identifiers per workout date.

---

### Inspect available CLI options

Show full help:

```bash
strava-weekly-export --help
```

Show help for the Intervals uploader:

```bash
strava-weekly-export intervals-push --help
```

---

## Output directories

By default the CLI writes to:

- `./out/`  
  → Weekly Strava exports  

- `./plans/`  
  → Archived planned weeks (full-week uploads only)  

Note:

- `--adhoc` uploads are **never archived** by design  

---

## Typical weekly usage

A normal weekly cycle looks like:

```bash
# 1. Export last week
strava-weekly-export --last-week

# 2. Paste JSON into ChatGPT and generate next week

# 3. Validate the new plan
strava-weekly-export intervals-push --planned planned_workouts.json --validate-only

# 4. Upload when happy
strava-weekly-export intervals-push --planned planned_workouts.json
```

This loop is the primary intended usage pattern of the tool.


---

## Repository layout

High-level structure:

- `cli.py`  
  Main entrypoint. Parses arguments, orchestrates exports and uploads.

- `auth.py`  
  Strava and Intervals token handling. Tokens are persisted under `./secrets`.

- `strava_client.py`  
  Strava API access: list activities, fetch details, map to export schema.

- `export_week.py`  
  Weekly aggregation and JSON rendering.

- `intervals_client.py`  
  Intervals.icu API client and upload logic.

- `workout_render.py`  
  Validation and rendering helpers for planned workouts.

- `plan_archive.py`  
  Archives uploaded plans to `./plans`.

- `./out`  
  Weekly Strava exports.

- `./plans`  
  Archived planned weeks.

---

## Authentication & setup

Environment variables expected:

- `STRAVA_CLIENT_ID`  
- `STRAVA_CLIENT_SECRET`  
- `INTERVALS_API_KEY`  
- `LOCAL_TIMEZONE` (optional)  

Tokens are persisted under `./secrets`.

---

## Safety rails & important gotchas

### Always validate before uploading

Use:

```bash
--validate-only
```

This prevents:
- Broken JSON  
- Malformed repeats  
- API rejections  

---

### Duplicate external IDs

Intervals.icu requires unique workout identifiers.  
If you re-upload a modified plan for the same dates:

- Either delete the old planned workouts in Intervals first, or  
- Change the workout names / IDs  

Otherwise Intervals may reject or silently ignore updates.

---

### Only Run workouts are uploaded

By design:
- Cycling, strength, yoga, etc. are ignored  
- You may describe them in the explanation, but do not include them in the JSON  

---

### This tool does not “auto-progress” your training

Progression logic is intentionally external:

- ChatGPT proposes structure  
- You review and adjust  
- You remain accountable for load, injury risk, and realism  

This is a planning assistant, not a coaching black box.

---

## Philosophy

This project is built around a few principles:

- **Data-driven planning beats vibes**  
- **Human judgement remains central**  
- **Transparency over automation**  
- **Repeatability over cleverness**  

The goal is not to “let AI run your training”, but to:

- Preserve training history  
- Make planning faster and more consistent  
- Enable intelligent iteration week by week  
