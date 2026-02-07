# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Rules

**NEVER modify the file `sources.json`** - This file contains personal calendar URLs and credentials configured by the user. Always use `sources_example.json` as a template for documentation.

## Project Overview

Automated iCal calendar monitoring and synchronization system. Downloads calendars from webcal URLs, detects changes, and generates a single timestamped result file for downstream processing.

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
python print_calendar_sync.py -f data_sync/20260206_053409_calendar_sync.json

# Explore available fields in calendars
python explore_fields.py

# Schedule via cron (hourly example)
0 * * * * /usr/bin/python3 /path/to/calendar_sync.py >> /var/log/calendar_sync.log 2>&1

# Archive a Google Calendar to another calendar
python archive_google_calendar.py SOURCE -a ARCHIVE

# Archive with dry-run (no modifications)
python archive_google_calendar.py SOURCE -a ARCHIVE -d

# Resume interrupted archive (skip duplicates)
python archive_google_calendar.py SOURCE -a ARCHIVE -r

# Google Calendar CRUD operations
python google_calendar_crud.py list
python google_calendar_crud.py show EVENT_ID
python google_calendar_crud.py create -s "Meeting" --start 2026-03-15T14:00 --end 2026-03-15T15:00
python google_calendar_crud.py update EVENT_ID --color tomato -l "Room A"
python google_calendar_crud.py delete EVENT_ID -y

# Compare calendars (reference vs proposition)
python compare_calendars.py data/etat_source.json data/etat_google_source.json
python compare_calendars.py REF_FILE PROP_FILE --summary
python compare_calendars.py REF_FILE PROP_FILE --from 2026-01-01 --to 2026-06-30 --json

# Import events from state file to Google Calendar
python import_to_google_calendar.py data/etat_source.json -c "Mon Calendrier"
python import_to_google_calendar.py data/etat_source.json -c "Mon Calendrier" -d
python import_to_google_calendar.py data/etat_source.json -c "Cal" --from 2026-01-01 --to 2026-06-30
python import_to_google_calendar.py --show-colors
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

### archive_google_calendar.py options

| Option | Description |
|--------|-------------|
| `source` | Name or ID of calendar to archive |
| `-a`, `--archive` | Name or ID of destination archive calendar (required) |
| `-d`, `--dry-run` | Simulate without making changes |
| `-r`, `--resume` | Resume interrupted archive (skip events already present) |

### google_calendar_crud.py

CLI for CRUD operations on Google Calendar events.

#### Commands

| Command | Description |
|---------|-------------|
| `list` | List events |
| `show` | Show event details |
| `create` | Create an event |
| `update` | Update an event |
| `delete` | Delete an event |

#### list options

| Option | Description |
|--------|-------------|
| `-c`, `--calendar` | Calendar name or ID (default: primary) |
| `--from` | Start date (YYYY-MM-DD) |
| `--to` | End date (YYYY-MM-DD) |
| `-q`, `--query` | Search text |
| `-n`, `--max-results` | Maximum number of events |
| `--json` | Output as JSON |

#### create options

| Option | Description |
|--------|-------------|
| `-s`, `--summary` | Event title (required) |
| `--start` | Start date/time (required) |
| `--end` | End date/time (required) |
| `-c`, `--calendar` | Calendar name or ID (default: primary) |
| `-l`, `--location` | Location |
| `-d`, `--description` | Description |
| `--color` | Color (name or 1-11) |
| `--all-day` | All-day event |
| `--timezone` | Timezone (default: Europe/Paris) |
| `--recurrence` | Recurrence rule (RRULE) |
| `--visibility` | public/private/confidential |
| `--transparency` | opaque/transparent |
| `--reminder` | Reminder in minutes (repeatable) |
| `--attendee` | Attendee email (repeatable) |
| `--json` | Output as JSON |

#### update options

| Option | Description |
|--------|-------------|
| `event_id` | Event ID (required) |
| `-c`, `--calendar` | Calendar name or ID |
| `-s`, `--summary` | Event title |
| `--start`, `--end` | Date/time |
| `-l`, `--location` | Location |
| `-d`, `--description` | Description |
| `--color` | Color (name or 1-11) |
| `--status` | confirmed/tentative/cancelled |
| `--visibility` | public/private/confidential |
| `--transparency` | opaque/transparent |
| `--add-reminder` | Add reminder in minutes |
| `--remove-reminders` | Remove all custom reminders |
| `--add-attendee` | Add attendee email |
| `--remove-attendee` | Remove attendee email |
| `--json` | Output as JSON |

#### delete options

| Option | Description |
|--------|-------------|
| `event_id` | Event ID (required) |
| `-c`, `--calendar` | Calendar name or ID |
| `-y`, `--yes` | Skip confirmation |
| `--send-updates` | Send cancellation (all/externalOnly/none) |

#### Available colors

| ID | Name |
|----|------|
| 1 | lavender |
| 2 | sage |
| 3 | grape |
| 4 | flamingo |
| 5 | banana |
| 6 | tangerine |
| 7 | peacock |
| 8 | graphite |
| 9 | blueberry |
| 10 | basil |
| 11 | tomato |

### compare_calendars.py

Compare two calendars (reference vs proposition) and display matches, differences, and missing events.

#### Options

| Option | Description |
|--------|-------------|
| `ref_file` | Reference calendar file (positional) |
| `prop_file` | Proposition calendar file (positional) |
| `--from` | Start date filter (YYYY-MM-DD) |
| `--to` | End date filter (YYYY-MM-DD) |
| `--summary` | Show summary only |
| `--json` | Output as JSON |

#### Result types

| Type | Description |
|------|-------------|
| `match` | Same time slot, same title/location |
| `modified` | Same time slot, different title/location |
| `missing` | In reference but not in proposition |
| `extra` | In proposition but not in reference |

### import_to_google_calendar.py

Import events from a state file to Google Calendar with automatic color assignment based on class patterns.

#### Options

| Option | Description |
|--------|-------------|
| `file` | State file to import (positional) |
| `-c`, `--calendar` | Target calendar name or ID |
| `-d`, `--dry-run` | Show what would be created without making changes |
| `--from` | Start date filter (YYYY-MM-DD) |
| `--to` | End date filter (YYYY-MM-DD) |
| `--colors` | JSON file with class-to-color mapping |
| `--show-colors` | Show class-to-color mapping and exit |
| `--json` | Output results as JSON |

#### Default class-to-color mapping

| Pattern | Color |
|---------|-------|
| `BACH INGE` | peacock (7) |
| `BTS CIEL` | sage (2) |
| `BTS SIO` | blueberry (9) |
| `EISI` | grape (3) |
| `B3 RNSPP` | tangerine (6) |
| `TSSNI` | flamingo (4) |
| `SEE` | banana (5) |
| `MPI` | basil (10) |
| `BACHELOR CPI` | lavender (1) |
| `BACHELOR CPLR` | tomato (11) |

Custom mapping via JSON file (see `class_colors_example.json`).

## Architecture

The system follows a pipeline pattern:

1. `Source` - Calendar source configuration (URL, SSL) with `load_all_configs()` factory
2. `DateFilter` - Filters events by global date range `[DATE_DEBUT, DATE_FIN]` (constants in source code)
3. `CalendarSource` - Downloads, parses and filters iCal events via `fetch()`
4. `CalendarSync` - Main orchestrator: change detection, state management, sync process

Key data classes:
- `Source` - Source configuration from `sources.json` via `load_all_configs(config_file)`, owns a `DateFilter`
- `DateFilter` - Global date range filter using `DATE_DEBUT`/`DATE_FIN` constants
- `CalendarSource` - Calendar downloader/parser with `events` dict
- `Event` - Calendar event representation with `to_dict()` and `from_dict()`
- `Change` - Single detected modification
- `ChangeType` - Enum for change categorization

Key functions:
- `save_result()` - Saves the single timestamped result file
- `format_event_for_notification()` - Converts event dates to display format

## Data Files

| File | Purpose |
|------|---------|
| `sources.json` | Calendar sources configuration (user-specific, gitignored) |
| `sources_example.json` | Example configuration template |
| `class_colors_example.json` | Example class-to-color mapping for import |
| `data/etat_{source}.json` | Validated calendar state for each source (dates in ISO format) |
| `data/calendar_sync.log` | Log file |
| `data_sync/{timestamp}_calendar_sync.json` | Sync result with config, per-source status and changes |

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

## Result File Format

The file `{timestamp}_calendar_sync.json` contains all sync results:

```json
{
  "timestamp": "20260206_080000",
  "status": "success",
  "config": {
    "config_file": "sources.json",
    "dry_run": false,
    "date_debut": "2025-08-01",
    "date_fin": "2026-07-31"
  },
  "sources": {
    "source_name": {
      "status": "success",
      "events_count": 200,
      "changes_count": 3,
      "changes": [
        {
          "type": "new_event",
          "event": {
            "uid": "event-123",
            "title": "Cours de maths",
            "location": "Salle A101",
            "start": "15/03/2026 14:00",
            "end": "15/03/2026 16:00",
            "description": "",
            "last_modified": "06/02/2026 08:00",
            "dtstamp": "06/02/2026 08:00",
            "status": ""
          }
        },
        {
          "type": "modified_event",
          "event": { "uid": "...", "title": "...", ... },
          "previous": { "uid": "...", "title": "...", ... },
          "changes": [
            {
              "type": "location_change",
              "field": "Salle",
              "old_value": "A101",
              "new_value": "B203"
            }
          ]
        },
        {
          "type": "deleted_event",
          "event": { "uid": "...", "title": "...", ... }
        }
      ]
    }
  }
}
```

### Change Types

| Type | Description |
|------|-------------|
| `new_event` | New event added |
| `modified_event` | Event modified (with list of field changes) |
| `deleted_event` | Event removed |
| `title_change` | Title changed |
| `location_change` | Location changed |
| `description_change` | Description changed |
| `status_change` | Status changed |
| `start_time_change` | Start date/time changed |
| `end_time_change` | End date/time changed |

### Status Values

| Status | Description |
|--------|-------------|
| `success` | All sources processed successfully |
| `partial` | Some sources failed, others succeeded |
| `error` | All sources failed |

## Date Filtering

Date filtering is configured globally via constants in `calendar_sync.py`:

```python
DATE_DEBUT = "2025-08-01"
DATE_FIN = "2026-07-31"
```

These apply to all sources. Events outside this range are ignored.

## Timezone and Date Display

Dates in result files are converted to local timezone and formatted for display:

```python
TIMEZONE = ZoneInfo("Europe/Paris")
DISPLAY_DATE_FORMAT = "%d/%m/%Y %H:%M"
```

Output example: `15/03/2026 14:30`

State files (`etat_{source}.json`) keep dates in original ISO format for accurate change detection.

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
