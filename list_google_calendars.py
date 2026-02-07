#!/usr/bin/env python3
"""
Liste les calendriers Google visibles avec leurs URLs iCal.
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pickle
import os
import json
import argparse

SCOPES = ['https://www.googleapis.com/auth/calendar']
CONFIG_FILE = 'config.json'


def load_config():
    """Charge la configuration depuis config.json."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_credentials():
    """Obtient les credentials Google, avec refresh si nécessaire."""
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


def format_date(date_str):
    """Convertit YYYY-MM-DD en DD-MM-YYYY."""
    if len(date_str) >= 10:
        return f"{date_str[8:10]}-{date_str[5:7]}-{date_str[0:4]}"
    return date_str


def format_datetime(dt_str):
    """Convertit une date/heure ISO en format français."""
    if not dt_str:
        return ""
    # Format: 2026-03-15T14:30:00+01:00
    date_part = dt_str[:10]
    time_part = dt_str[11:16] if len(dt_str) > 11 else ""
    formatted_date = format_date(date_part)
    if time_part:
        return f"{formatted_date} {time_part}"
    return formatted_date


def get_calendar_events(service, cal_id):
    """Récupère tous les événements d'un calendrier."""
    events = []
    page_token = None

    while True:
        result = service.events().list(
            calendarId=cal_id,
            singleEvents=True,
            orderBy='startTime',
            pageToken=page_token
        ).execute()

        events.extend(result.get('items', []))
        page_token = result.get('nextPageToken')

        if not page_token:
            break

    return events


def get_calendar_stats(service, cal_id):
    """Récupère les statistiques d'un calendrier (nombre d'événements, premier, dernier)."""
    events = get_calendar_events(service, cal_id)

    if not events:
        return 0, None, None

    def get_date(event):
        start = event.get('start', {})
        date_str = start.get('dateTime', start.get('date', ''))[:10]
        return format_date(date_str)

    first_date = get_date(events[0])
    last_date = get_date(events[-1])

    return len(events), first_date, last_date


def display_events(service, cal_id):
    """Affiche les événements d'un calendrier."""
    events = get_calendar_events(service, cal_id)

    if not events:
        print("    Aucun événement")
        return

    print(f"    Événements ({len(events)}) :")
    for event in events:
        start = event.get('start', {})
        start_str = start.get('dateTime', start.get('date', ''))
        title = event.get('summary', '(sans titre)')
        location = event.get('location', '')

        date_display = format_datetime(start_str)
        loc_str = f" @ {location}" if location else ""

        print(f"      {date_display} | {title}{loc_str}")


def get_first_event_date(service, cal_id):
    """Récupère la date du premier événement d'un calendrier (format ISO pour tri)."""
    result = service.events().list(
        calendarId=cal_id,
        singleEvents=True,
        orderBy='startTime',
        maxResults=1
    ).execute()

    events = result.get('items', [])
    if not events:
        return None

    start = events[0].get('start', {})
    return start.get('dateTime', start.get('date', ''))


def display_calendar(service, cal, show_stats, show_events):
    """Affiche les informations d'un calendrier."""
    cal_id = cal.get('id', '')
    name = cal.get('summary', '(sans nom)')
    access_role = cal.get('accessRole', '')
    primary = " [Principal]" if cal.get('primary') else ""

    print(f"  {name}{primary}")
    print(f"    ID: {cal_id}")
    print(f"    Accès: {access_role}")

    if show_stats:
        event_count, first, last = get_calendar_stats(service, cal_id)
        print(f"    Événements: {event_count}")
        if first and last:
            print(f"    Période: {first} → {last}")

    if show_events:
        display_events(service, cal_id)

    print()


def list_calendars(show_stats=False, show_events=False, calendar_filter=None, sort_by_first=False):
    """Liste tous les calendriers visibles (hors exclusions)."""
    config = load_config()
    exclude_ids = config.get('exclude_calendar', [])

    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)

    calendars = service.calendarList().list().execute()

    # Filtrer les calendriers
    filtered_cals = []
    for cal in calendars.get('items', []):
        cal_id = cal.get('id', '')
        name = cal.get('summary', '(sans nom)')

        if cal_id in exclude_ids:
            continue

        if calendar_filter:
            if calendar_filter not in cal_id and calendar_filter.lower() not in name.lower():
                continue

        filtered_cals.append(cal)

    # Trier par premier événement si demandé
    if sort_by_first:
        print("Récupération des dates de premier événement...")
        for cal in filtered_cals:
            cal['_first_event'] = get_first_event_date(service, cal['id'])

        # Trier: calendriers avec événements d'abord (par date), puis sans événements
        filtered_cals.sort(key=lambda c: (c['_first_event'] is None, c['_first_event'] or ''))
        print()

    # Afficher les calendriers
    for cal in filtered_cals:
        display_calendar(service, cal, show_stats, show_events)

    print(f"Total: {len(filtered_cals)} calendrier(s)")


def main():
    parser = argparse.ArgumentParser(
        description="Liste les calendriers Google visibles"
    )
    parser.add_argument(
        '-s', '--stat',
        action='store_true',
        help="Afficher les statistiques (nombre d'événements, dates)"
    )
    parser.add_argument(
        '-e', '--events',
        action='store_true',
        help="Lister les événements"
    )
    parser.add_argument(
        '-t', '--tri',
        action='store_true',
        help="Trier par date du premier événement"
    )
    parser.add_argument(
        '-c', '--calendar',
        help="Filtrer par ID ou nom de calendrier"
    )

    args = parser.parse_args()
    list_calendars(
        show_stats=args.stat,
        show_events=args.events,
        calendar_filter=args.calendar,
        sort_by_first=args.tri
    )


if __name__ == "__main__":
    main()
