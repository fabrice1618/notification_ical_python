# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Rules

**NEVER modify the file `sources.json`** - This file contains personal calendar URLs and credentials configured by the user. Always use `sources_example.json` as a template for documentation.

## Project Overview

Automated iCal calendar monitoring and synchronization system. Downloads calendars from webcal URLs, detects changes, and generates timestamped notifications for downstream processing.

## Notification Types

| Type | Description | Examples |
|------|-------------|----------|
| `information` | Minor changes | Room, title, description |
| `notification` | Important changes | Dates/times, new/deleted events |
| `error` | Errors | Connection, iCal format |

## Commands

```bash
# Install dependencies
pip install icalendar requests

# Run synchronization for a source
python calendar_sync.py -s cours

# With custom config file
python calendar_sync.py -s cours --config my_sources.json

# Dry-run: detect changes without saving state
python calendar_sync.py -s cours -d

# With notification file generation
python calendar_sync.py -s cours -n

# Dry-run with notifications
python calendar_sync.py -s cours -d -n

# Explore available fields in calendars
python explore_fields.py

# Schedule via cron (hourly example)
0 * * * * /usr/bin/python3 /path/to/calendar_sync.py -s cours -n >> /var/log/calendar_sync.log 2>&1
```

| Option | Description |
|--------|-------------|
| `-s`, `--source` | Source name to sync (required) |
| `--config` | Config file path (default: sources.json) |
| `-d`, `--dry-run` | Run without saving state (etat_{source}.json is not modified) |
| `-n`, `--notification` | Generate notification files in notifications/ |

## Architecture

The system follows a pipeline pattern:

1. `Source` - Calendar source configuration (URL, SSL) with `load_config()` factory
2. `DateFilter` - Filters events by date range `[date_debut, date_fin]`
3. `CalendarSource` - Downloads, parses and filters iCal events via `fetch()`
4. `CalendarSync` - Main orchestrator: change detection, state management, sync process

Key data classes:
- `Source` - Source configuration from `sources.json` via `load_config(name, config_file)`, owns a `DateFilter`
- `DateFilter` - Date range filter with `filter()` method
- `CalendarSource` - Calendar downloader/parser with `events` dict and `iter_events()` generator
- `Event` - Calendar event representation with `to_dict()` and `from_dict()`
- `Change` - Single detected modification with notification type
- `ChangeType` / `NotificationType` - Enums for change categorization

Key functions:
- `save_notification()` - Saves timestamped change notification files
- `save_process()` - Saves process report files

## Data Files

| File | Purpose |
|------|---------|
| `sources.json` | Calendar sources configuration (user-specific, gitignored) |
| `sources_example.json` | Example configuration template |
| `data/etat_{source}.json` | Validated calendar state for each source |
| `data/calendar_sync.log` | Log file |
| `notifications/process_{timestamp}.json` | Process report (status, config, counters) |
| `notifications/{source}_{timestamp}.json` | Change notifications (only with --notification) |

## Processing Flow

```
1. Load config (sources.json)
2. Load current state (etat_{source}.json)
3. Download iCal calendar
4. Parse events
5. Filter by date_debut/date_fin (if configured)
6. Detect changes
7. Update validated state (etat_{source}.json)  [skipped with --dry-run]
8. Save process report (process_{timestamp}.json)
9. Save change notification                      [only with --notification]
```

## Source Configuration

```json
{
  "source_name": {
    "url": "webcal://example.com/calendar.ics",
    "description": "Description",
    "date_debut": "2026-01-01",
    "date_fin": "2026-06-30",
    "verify_ssl": true
  }
}
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `url` | Yes | iCal URL (webcal:// or https://) |
| `description` | No | Source description |
| `date_debut` | No | Ignore events before this date (YYYY-MM-DD) |
| `date_fin` | No | Ignore events after this date (YYYY-MM-DD) |
| `verify_ssl` | No | Verify SSL certificate (default: true) |
