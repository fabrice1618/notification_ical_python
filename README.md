# Calendar Sync & Google Calendar Tools

Automated iCal calendar monitoring and synchronization system with Google Calendar integration.

## Features

- **Calendar Sync**: Download calendars from webcal URLs, detect changes, generate timestamped results
- **Google Calendar CRUD**: Full create/read/update/delete operations on Google Calendar events
- **Archive Tool**: Transfer events between Google calendars
- **Calendar Explorer**: List and explore Google calendars

## Installation

```bash
pip install icalendar requests google-auth-oauthlib google-api-python-client
```

For Google Calendar tools, you need:
1. A `credentials.json` file from Google Cloud Console
2. Run any Google tool once to authenticate (creates `token.pickle`)

## Quick Start

### Calendar Sync (iCal monitoring)

```bash
# Run synchronization
python calendar_sync.py

# Dry-run mode
python calendar_sync.py -d

# Display latest results
python print_calendar_sync.py
```

### Google Calendar CRUD

```bash
# List events
python google_calendar_crud.py list
python google_calendar_crud.py list -c "Work" --from 2026-03-01 --to 2026-03-31

# Show event details
python google_calendar_crud.py show EVENT_ID

# Create event
python google_calendar_crud.py create \
    -s "Meeting" \
    --start 2026-03-15T14:00 \
    --end 2026-03-15T15:00 \
    -l "Room A" \
    --color blueberry

# Create all-day event
python google_calendar_crud.py create \
    -s "Holiday" \
    --start 2026-03-25 \
    --end 2026-03-26 \
    --all-day

# Update event
python google_calendar_crud.py update EVENT_ID \
    --color tomato \
    -l "New Room"

# Delete event
python google_calendar_crud.py delete EVENT_ID -y
```

### Other Google Calendar Tools

```bash
# List calendars
python list_google_calendars.py
python list_google_calendars.py -s  # with stats

# Archive calendar
python archive_google_calendar.py SOURCE -a ARCHIVE
python archive_google_calendar.py SOURCE -a ARCHIVE -r  # resume mode
```

## Available Colors

| ID | Name | Hex |
|----|------|-----|
| 1 | lavender | #a4bdfc |
| 2 | sage | #7ae7bf |
| 3 | grape | #dbadff |
| 4 | flamingo | #ff887c |
| 5 | banana | #fbd75b |
| 6 | tangerine | #ffb878 |
| 7 | peacock | #46d6db |
| 8 | graphite | #e1e1e1 |
| 9 | blueberry | #5484ed |
| 10 | basil | #51b749 |
| 11 | tomato | #dc2127 |

## Configuration

### Calendar Sync Sources

Create `sources.json` (see `sources_example.json`):

```json
{
  "source_name": {
    "url": "webcal://example.com/calendar.ics",
    "description": "My calendar",
    "verify_ssl": true
  }
}
```

### Google Calendar Exclusions

Create `config.json` to exclude calendars from listing:

```json
{
  "exclude_calendar": ["calendar_id_to_hide@group.calendar.google.com"]
}
```

## Data Files

| File | Purpose |
|------|---------|
| `sources.json` | Calendar sources configuration |
| `data/etat_{source}.json` | Sync state per source |
| `data_sync/{timestamp}_calendar_sync.json` | Sync results |
| `token.pickle` | Google OAuth token |
| `credentials.json` | Google API credentials |

## Cron Example

```bash
# Sync every hour
0 * * * * /usr/bin/python3 /path/to/calendar_sync.py >> /var/log/calendar_sync.log 2>&1
```

## License

MIT
