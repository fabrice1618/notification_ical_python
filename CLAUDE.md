# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Rules

**NEVER modify the file `sources.json`** - This file contains personal calendar URLs and credentials configured by the user. Always use `sources_example.json` as a template for documentation.

## Project Overview

Automated iCal calendar monitoring and synchronization system. Downloads calendars from webcal URLs, detects changes, and generates timestamped notifications for downstream processing.

## Commands

```bash
# Install dependencies
pip install icalendar requests

# Run synchronization (all sources)
python calendar_sync.py

# With custom config file
python calendar_sync.py --config my_sources.json

# Dry-run: detect changes without saving state
python calendar_sync.py -d

# Display latest sync result
python print_calendar_sync.py

# Display specific result file
python print_calendar_sync.py -f notifications/20260206_053409_calendar_sync.json

# Explore available fields in calendars
python explore_fields.py

# Schedule via cron (hourly example)
0 * * * * /usr/bin/python3 /path/to/calendar_sync.py >> /var/log/calendar_sync.log 2>&1
```

### calendar_sync.py options

| Option | Description |
|--------|-------------|
| `--config` | Config file path (default: sources.json) |
| `-d`, `--dry-run` | Run without saving state (etat_{source}.json is not modified) |

### print_calendar_sync.py options

| Option | Description |
|--------|-------------|
| `-f`, `--file` | Result file to display (default: latest) |

## Architecture

The system follows a pipeline pattern:

1. `Source` - Calendar source configuration (URL, SSL) with `load_config()` factory
2. `DateFilter` - Filters events by global date range `[DATE_DEBUT, DATE_FIN]` (constants in source code)
3. `CalendarSource` - Downloads, parses and filters iCal events via `fetch()`
4. `CalendarSync` - Main orchestrator: change detection, state management, sync process

Key data classes:
- `Source` - Source configuration from `sources.json` via `load_config(name, config_file)` or `load_all_configs(config_file)`, owns a `DateFilter`
- `DateFilter` - Global date range filter using `DATE_DEBUT`/`DATE_FIN` constants
- `CalendarSource` - Calendar downloader/parser with `events` dict and `iter_events()` generator
- `Event` - Calendar event representation with `to_dict()` and `from_dict()`
- `Change` - Single detected modification
- `ChangeType` - Enum for change categorization

Key functions:
- `save_notification()` - Saves timestamped change notification files
- `save_process()` - Saves process report files

## Data Files

| File | Purpose |
|------|---------|
| `sources.json` | Calendar sources configuration (user-specific, gitignored) |
| `sources_example.json` | Example configuration template |
| `data/etat_{source}.json` | Validated calendar state for each source (dates in source format) |
| `data/calendar_sync.log` | Log file |
| `notifications/{timestamp}_calendar_sync.json` | Sync result with config, per-source status and changes |

## Processing Flow

```
1. Load all sources from config (sources.json)
2. For each source:
   a. Load current state (etat_{source}.json)
   b. Download iCal calendar
   c. Parse events
   d. Filter by DATE_DEBUT/DATE_FIN (global constants in source code)
   e. Detect changes
   f. Update validated state (etat_{source}.json)  [skipped with --dry-run]
   g. On error: capture and continue to next source
3. Save result file ({timestamp}_calendar_sync.json)
```

## Date Filtering

Date filtering is configured globally via constants in `calendar_sync.py`:

```python
DATE_DEBUT = "2026-01-01"
DATE_FIN = "2026-06-30"
```

These apply to all sources. Events outside this range are ignored.

## Timezone and Date Display

Dates are converted to local timezone and formatted for display:

```python
TIMEZONE = ZoneInfo("Europe/Paris")
DISPLAY_DATE_FORMAT = "%d/%m/%Y %H:%M"
```

Output example: `15/03/2026 14:30`

## Source Configuration

```json
{
  "source_name": {
    "url": "webcal://example.com/calendar.ics",
    "description": "Description",
    "verify_ssl": true
  }
}
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `url` | Yes | iCal URL (webcal:// or https://) |
| `description` | No | Source description |
| `verify_ssl` | No | Verify SSL certificate (default: true) |
