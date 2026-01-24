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

# Explore available fields in calendars
python explore_fields.py

# Schedule via cron (hourly example)
0 * * * * /usr/bin/python3 /path/to/calendar_sync.py -s cours >> /var/log/calendar_sync.log 2>&1
```

## Architecture

The system follows a pipeline pattern:

1. `CalendarSync` - Main orchestrator that coordinates the sync process
2. `ChangeDetector` - Compares events and categorizes changes by type

Key data classes:
- `Event` - Calendar event representation with `to_dict()` and `from_dict()`
- `Change` - Single detected modification with notification type
- `ChangeType` / `NotificationType` - Enums for change categorization

Key functions:
- `load_sources_config()` - Loads multi-source configuration
- `save_notification()` - Saves timestamped notification files

## Data Files

| File | Purpose |
|------|---------|
| `sources.json` | Calendar sources configuration (user-specific, gitignored) |
| `sources_example.json` | Example configuration template |
| `etat_{source}.json` | Validated calendar state for each source |
| `calendar_sync.log` | Log file |
| `notifications/{source}_{timestamp}.json` | Timestamped notification files |

## Processing Flow

```
1. Load config (sources.json)
2. Load current state (etat_{source}.json)
3. Download iCal calendar
4. Parse events
5. Filter by date_limite (if configured)
6. Detect changes
7. Update validated state (etat_{source}.json)
8. Generate timestamped notification
```

## Source Configuration

```json
{
  "source_name": {
    "url": "webcal://example.com/calendar.ics",
    "description": "Description",
    "date_limite": "2026-01-01",
    "verify_ssl": true
  }
}
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `url` | Yes | iCal URL (webcal:// or https://) |
| `description` | No | Source description |
| `date_limite` | No | Ignore events before this date (YYYY-MM-DD) |
| `verify_ssl` | No | Verify SSL certificate (default: true) |
