#!/usr/bin/env python3
"""
Import events from a state file to a Google Calendar.

Reads events from a JSON state file (e.g., etat_school1.json) and creates them
in a specified Google Calendar. Supports dry-run mode and automatic color
assignment based on class patterns.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
import pickle
import os

SCOPES = ['https://www.googleapis.com/auth/calendar']
DEFAULT_TIMEZONE = 'Europe/Paris'
DEFAULT_RATE_LIMIT = 0.5  # Seconds between API calls to avoid rate limiting

# Color mapping: name -> colorId
COLORS = {
    'lavender': '1',
    'sage': '2',
    'grape': '3',
    'flamingo': '4',
    'banana': '5',
    'tangerine': '6',
    'peacock': '7',
    'graphite': '8',
    'blueberry': '9',
    'basil': '10',
    'tomato': '11',
}

COLOR_NAMES = {v: k for k, v in COLORS.items()}

# Default class-to-color mapping
# Pattern (regex or substring) -> color name
DEFAULT_CLASS_COLORS = {
    r"BACH\s*INGE": "peacock",      # Bachelor Ingenieur
    r"BTS\s*CIEL": "sage",          # BTS CIEL
    r"BTS\s*SIO": "blueberry",      # BTS SIO
    r"EISI": "grape",               # EISI
    r"B3\s*RNSPP": "tangerine",     # B3 RNSPP
    r"TSSNI": "flamingo",           # TSSNI
    r"SEE": "banana",               # SEE
    r"MPI": "basil",                # MPI
    r"BACHELOR\s*CPI": "lavender",  # Bachelor CPI
    r"BACHELOR\s*CPLR": "tomato",   # Bachelor CPLR
}


def get_credentials():
    """Get Google credentials, refreshing if needed."""
    creds = None

    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds


def find_calendar(service, name_or_id):
    """Find a calendar by name or ID."""
    calendars = service.calendarList().list().execute()

    for cal in calendars.get('items', []):
        cal_id = cal.get('id', '')
        name = cal.get('summary', '')

        if name_or_id == cal_id or name_or_id.lower() == name.lower():
            return cal

    return None


def get_calendar_id(service, calendar_arg):
    """Return the calendar ID (primary if not specified)."""
    if not calendar_arg:
        return 'primary'

    cal = find_calendar(service, calendar_arg)
    if not cal:
        print(f"Erreur: Calendrier '{calendar_arg}' introuvable")
        sys.exit(1)

    return cal['id']


def load_events(file_path: str) -> dict:
    """Load events from a JSON state file."""
    path = Path(file_path)
    if not path.exists():
        print(f"Erreur: Fichier introuvable: {file_path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_class_colors(config_file: str) -> dict:
    """Load class-to-color mapping from a JSON file."""
    if not config_file:
        return DEFAULT_CLASS_COLORS.copy()

    path = Path(config_file)
    if not path.exists():
        print(f"Erreur: Fichier de configuration introuvable: {config_file}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_color_for_event(title: str, class_colors: dict) -> str | None:
    """Determine the color for an event based on its title."""
    for pattern, color_name in class_colors.items():
        if re.search(pattern, title, re.IGNORECASE):
            return COLORS.get(color_name.lower())
    return None


def parse_event_datetime(dt_str: str) -> tuple[str | None, bool]:
    """
    Parse datetime from state file format.
    Returns (iso_string, is_all_day).
    """
    if not dt_str:
        return None, False

    # Handle ISO format with timezone
    if "+" in dt_str or dt_str.endswith("Z"):
        dt_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_str)
        # Convert to local timezone
        local_dt = dt.astimezone(ZoneInfo(DEFAULT_TIMEZONE))
        return local_dt.isoformat(), False

    # Naive datetime
    try:
        dt = datetime.fromisoformat(dt_str)
        local_dt = dt.replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE))
        return local_dt.isoformat(), False
    except ValueError:
        return None, False


def build_google_event(event: dict, class_colors: dict) -> dict:
    """Build a Google Calendar event body from a state file event."""
    body = {}

    # Title
    title = event.get("title", "")
    body["summary"] = title

    # Location
    if event.get("location"):
        body["location"] = event["location"]

    # Description
    if event.get("description"):
        body["description"] = event["description"]

    # Start/End
    start_str, _ = parse_event_datetime(event.get("start", ""))
    end_str, _ = parse_event_datetime(event.get("end", ""))

    if start_str:
        body["start"] = {"dateTime": start_str, "timeZone": DEFAULT_TIMEZONE}
    if end_str:
        body["end"] = {"dateTime": end_str, "timeZone": DEFAULT_TIMEZONE}

    # Color based on class
    color_id = get_color_for_event(title, class_colors)
    if color_id:
        body["colorId"] = color_id

    return body


def format_event_for_display(event: dict, color_id: str | None) -> str:
    """Format an event for dry-run display."""
    title = event.get("title", "(sans titre)")
    location = event.get("location", "")
    start = event.get("start", "")
    end = event.get("end", "")

    # Parse and format dates
    start_dt, _ = parse_event_datetime(start)
    end_dt, _ = parse_event_datetime(end)

    if start_dt:
        start_display = start_dt[:16].replace("T", " ")
    else:
        start_display = start

    if end_dt:
        end_display = end_dt[11:16] if start_dt and end_dt[:10] == start_dt[:10] else end_dt[:16].replace("T", " ")
    else:
        end_display = end

    color_str = ""
    if color_id:
        color_name = COLOR_NAMES.get(color_id, color_id)
        color_str = f" [{color_name}]"

    loc_str = f" @ {location}" if location else ""

    return f"{start_display}-{end_display} | {title}{loc_str}{color_str}"


def import_events(
    events: dict,
    calendar_id: str | None,
    class_colors: dict,
    service,
    dry_run: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    rate_limit: float = DEFAULT_RATE_LIMIT,
) -> dict:
    """Import events to Google Calendar."""
    results = {
        "total": 0,
        "created": 0,
        "skipped": 0,
        "errors": [],
    }

    sorted_events = sorted(
        events.values(),
        key=lambda e: e.get("start", "")
    )

    for event in sorted_events:
        # Filter by date if specified
        start_str = event.get("start", "")
        if start_str:
            try:
                if "+" in start_str or start_str.endswith("Z"):
                    start_str = start_str.replace("Z", "+00:00")
                    start_dt = datetime.fromisoformat(start_str)
                    start_dt = start_dt.replace(tzinfo=None)
                else:
                    start_dt = datetime.fromisoformat(start_str)

                if date_from and start_dt < date_from:
                    continue
                if date_to and start_dt > date_to:
                    continue
            except ValueError:
                pass

        results["total"] += 1

        google_event = build_google_event(event, class_colors)
        color_id = google_event.get("colorId")

        if dry_run:
            print(f"  [DRY-RUN] {format_event_for_display(event, color_id)}")
            results["created"] += 1
            continue

        try:
            created = service.events().insert(
                calendarId=calendar_id,
                body=google_event
            ).execute()

            print(f"  [OK] {format_event_for_display(event, color_id)}")
            results["created"] += 1

        except HttpError as e:
            error_msg = f"{event.get('title', 'Unknown')}: {e.reason}"
            results["errors"].append(error_msg)
            print(f"  [ERREUR] {event.get('title', 'Unknown')}: {e.reason}")

        # Rate limiting to avoid API quota errors
        if rate_limit > 0:
            time.sleep(rate_limit)

    return results


def show_color_mapping(class_colors: dict):
    """Display the class-to-color mapping."""
    print("Correspondance classes -> couleurs:")
    print()
    for pattern, color_name in class_colors.items():
        color_id = COLORS.get(color_name.lower(), "?")
        print(f"  {pattern:20} -> {color_name} ({color_id})")
    print()
    print("Couleurs disponibles:")
    for name, cid in COLORS.items():
        print(f"  {cid:2}: {name}")


def parse_date(date_str: str) -> datetime:
    """Parse a date string (YYYY-MM-DD) to datetime."""
    return datetime.strptime(date_str, "%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(
        description="Import events from a state file to Google Calendar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s data/etat_school1.json -c "Mon Calendrier"
  %(prog)s data/etat_school1.json -c "Mon Calendrier" -d
  %(prog)s data/etat_school2.json -c "SCHOOL2" --from 2026-01-01 --to 2026-06-30
  %(prog)s --show-colors

Color mapping file format (JSON):
  {
    "BACH\\\\s*INGE": "peacock",
    "BTS\\\\s*CIEL": "sage",
    "EISI": "grape"
  }
"""
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="State file to import (e.g., data/etat_school1.json)"
    )
    parser.add_argument(
        "-c", "--calendar",
        required=False,
        help="Target calendar name or ID"
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Show what would be created without making changes"
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        help="Start date filter (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        help="End date filter (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--colors",
        help="JSON file with class-to-color mapping"
    )
    parser.add_argument(
        "--show-colors",
        action="store_true",
        help="Show class-to-color mapping and exit"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=DEFAULT_RATE_LIMIT,
        metavar="SECONDS",
        help=f"Delay between API calls (default: {DEFAULT_RATE_LIMIT}s)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Load class colors
    class_colors = load_class_colors(args.colors)

    # Show colors mode
    if args.show_colors:
        show_color_mapping(class_colors)
        return

    # Validate required arguments
    if not args.file:
        parser.print_help()
        sys.exit(1)

    if not args.calendar and not args.dry_run:
        print("Erreur: --calendar (-c) est requis (sauf en mode --dry-run)")
        sys.exit(1)

    # Parse date filters
    date_from = parse_date(args.date_from) if args.date_from else None
    date_to = parse_date(args.date_to) if args.date_to else None

    # Load events
    events = load_events(args.file)
    print(f"Fichier: {args.file} ({len(events)} evenements)")

    # Connect to Google Calendar (unless dry-run without calendar)
    service = None
    calendar_id = None

    if not args.dry_run or args.calendar:
        creds = get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        calendar_id = get_calendar_id(service, args.calendar) if args.calendar else None

    if args.calendar:
        cal = find_calendar(service, args.calendar)
        cal_name = cal.get("summary", args.calendar) if cal else args.calendar
        print(f"Calendrier: {cal_name}")

    if args.dry_run:
        print("Mode: DRY-RUN (aucune modification)")

    print()

    # Import events
    results = import_events(
        events,
        calendar_id,
        class_colors,
        service,
        dry_run=args.dry_run,
        date_from=date_from,
        date_to=date_to,
        rate_limit=args.rate_limit,
    )

    # Summary
    print()
    print("=== Resume ===")
    print(f"Total: {results['total']}")
    print(f"Crees: {results['created']}")

    if results["errors"]:
        print(f"Erreurs: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  - {error}")

    if args.json:
        print()
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
