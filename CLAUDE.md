# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated iCal calendar monitoring and synchronization system. Downloads calendars from webcal URLs, detects changes, auto-applies some modifications based on business rules, and generates notifications for changes requiring manual approval.

## Business Rules

**Auto-approved changes** (applied automatically):
- Room/location changes
- Title changes

**Changes requiring approval** (generate pending notifications):
- Start date/time changes
- End date/time changes

## Commands

```bash
# Install dependencies
pip install icalendar requests

# Run synchronization
python calendar_sync.py

# Schedule via cron (hourly example)
0 * * * * /usr/bin/python3 /path/to/calendar_sync.py >> /var/log/calendar_sync.log 2>&1
```

## Architecture

The system follows a pipeline pattern:

1. `CalendarSync` - Main orchestrator that coordinates the sync process
2. `ChangeDetector` - Compares events and categorizes changes by type
3. `StateManager` - Applies auto-approved changes, preserves pending changes
4. `NotificationManager` - Handles notification persistence and approval workflow

Key data classes:
- `Event` - Calendar event representation
- `Change` - Single detected modification with approval status
- `ChangeType` / `ActionType` - Enums for change categorization

## Data Files

| File | Purpose |
|------|---------|
| `etat_actuel.json` | Validated calendar state (approved changes only) |
| `new.json` | Latest downloaded state from source |
| `notifications.json` | All change notifications with approval status |

## Processing Flow

```
fetch_calendar() → parse_events() → save to new.json → compare with etat_actuel.json
→ apply auto-approved changes → generate notifications → update etat_actuel.json
```

Date/time changes remain in `new.json` until explicitly approved via `approve_notification_by_uid()`.
