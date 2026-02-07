#!/usr/bin/env python3
"""
CRUD operations for Google Calendar events.

Commands:
  list     List events
  show     Show event details
  create   Create an event
  update   Update an event
  delete   Delete an event
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
import pickle
import os
import argparse
import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SCOPES = ['https://www.googleapis.com/auth/calendar']
DEFAULT_TIMEZONE = 'Europe/Paris'

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

COLOR_HEX = {
    '1': '#a4bdfc',
    '2': '#7ae7bf',
    '3': '#dbadff',
    '4': '#ff887c',
    '5': '#fbd75b',
    '6': '#ffb878',
    '7': '#46d6db',
    '8': '#e1e1e1',
    '9': '#5484ed',
    '10': '#51b749',
    '11': '#dc2127',
}


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


def find_calendar(service, name_or_id):
    """Trouve un calendrier par nom ou ID."""
    calendars = service.calendarList().list().execute()

    for cal in calendars.get('items', []):
        cal_id = cal.get('id', '')
        name = cal.get('summary', '')

        if name_or_id == cal_id or name_or_id.lower() == name.lower():
            return cal

    return None


def get_calendar_id(service, calendar_arg):
    """Retourne l'ID du calendrier (primary si non spécifié)."""
    if not calendar_arg:
        return 'primary'

    cal = find_calendar(service, calendar_arg)
    if not cal:
        print(f"Erreur: Calendrier '{calendar_arg}' introuvable")
        print("Utilisez list_google_calendars.py pour voir les calendriers disponibles")
        sys.exit(1)

    return cal['id']


def parse_datetime(dt_str, timezone=None):
    """
    Parse a datetime string.

    Formats supportés:
    - YYYY-MM-DD (date seule, all-day)
    - YYYY-MM-DDTHH:MM:SS
    - YYYY-MM-DDTHH:MM
    - YYYY-MM-DD HH:MM:SS
    - YYYY-MM-DD HH:MM
    """
    if not dt_str:
        return None, False

    tz = ZoneInfo(timezone) if timezone else ZoneInfo(DEFAULT_TIMEZONE)

    # Date seule
    if len(dt_str) == 10 and '-' in dt_str:
        return dt_str, True

    # Normaliser le séparateur
    dt_str = dt_str.replace(' ', 'T')

    # Ajouter les secondes si manquantes
    if len(dt_str) == 16:
        dt_str += ':00'

    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt.isoformat(), False
    except ValueError:
        return None, False


def parse_color(color_input):
    """
    Parse color input (name or ID).

    Returns colorId (1-11) or None if invalid.
    """
    if not color_input:
        return None

    # Direct ID
    if color_input in COLOR_HEX:
        return color_input

    # Name lookup
    color_lower = color_input.lower()
    if color_lower in COLORS:
        return COLORS[color_lower]

    return None


def format_datetime_display(dt_dict):
    """Format start/end dict for display."""
    if not dt_dict:
        return ""

    if 'date' in dt_dict:
        # All-day event
        date_str = dt_dict['date']
        return f"{date_str[8:10]}/{date_str[5:7]}/{date_str[0:4]}"

    if 'dateTime' in dt_dict:
        dt_str = dt_dict['dateTime']
        # Format: 2026-03-15T14:30:00+01:00
        date_part = dt_str[:10]
        time_part = dt_str[11:16] if len(dt_str) > 11 else ""
        formatted_date = f"{date_part[8:10]}/{date_part[5:7]}/{date_part[0:4]}"
        if time_part:
            return f"{formatted_date} {time_part}"
        return formatted_date

    return ""


def get_color_name(color_id):
    """Get color name from colorId."""
    for name, cid in COLORS.items():
        if cid == color_id:
            return name
    return None


def format_event_display(event, verbose=False):
    """Format event for display."""
    event_id = event.get('id', '')
    summary = event.get('summary', '(sans titre)')
    location = event.get('location', '')
    description = event.get('description', '')
    start = format_datetime_display(event.get('start', {}))
    end = format_datetime_display(event.get('end', {}))
    color_id = event.get('colorId', '')
    status = event.get('status', '')
    visibility = event.get('visibility', '')
    transparency = event.get('transparency', '')
    recurrence = event.get('recurrence', [])
    attendees = event.get('attendees', [])
    reminders = event.get('reminders', {})

    lines = []

    if verbose:
        lines.append(f"ID: {event_id}")
        lines.append(f"Titre: {summary}")
        lines.append(f"Début: {start}")
        lines.append(f"Fin: {end}")

        if location:
            lines.append(f"Lieu: {location}")
        if description:
            lines.append(f"Description: {description}")
        if color_id:
            color_name = get_color_name(color_id)
            color_hex = COLOR_HEX.get(color_id, '')
            lines.append(f"Couleur: {color_name or color_id} ({color_hex})")
        if status and status != 'confirmed':
            lines.append(f"Statut: {status}")
        if visibility and visibility != 'default':
            lines.append(f"Visibilité: {visibility}")
        if transparency and transparency != 'opaque':
            lines.append(f"Transparence: {transparency}")
        if recurrence:
            lines.append(f"Récurrence: {', '.join(recurrence)}")
        if attendees:
            emails = [a.get('email', '') for a in attendees]
            lines.append(f"Participants: {', '.join(emails)}")
        if reminders.get('overrides'):
            mins = [str(r.get('minutes', 0)) for r in reminders['overrides']]
            lines.append(f"Rappels: {', '.join(mins)} min")
    else:
        loc_str = f" @ {location}" if location else ""
        color_str = f" [{get_color_name(color_id)}]" if color_id else ""
        lines.append(f"{start} - {end} | {summary}{loc_str}{color_str}")
        lines.append(f"  ID: {event_id}")

    return '\n'.join(lines)


def output_json(data):
    """Output data as JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def list_events(service, cal_id, time_min=None, time_max=None, query=None, max_results=None):
    """List events from a calendar."""
    params = {
        'calendarId': cal_id,
        'singleEvents': True,
        'orderBy': 'startTime',
    }

    if time_min:
        dt, is_date = parse_datetime(time_min)
        if dt:
            if is_date:
                params['timeMin'] = f"{dt}T00:00:00Z"
            else:
                params['timeMin'] = dt

    if time_max:
        dt, is_date = parse_datetime(time_max)
        if dt:
            if is_date:
                params['timeMax'] = f"{dt}T23:59:59Z"
            else:
                params['timeMax'] = dt

    if query:
        params['q'] = query

    if max_results:
        params['maxResults'] = max_results

    events = []
    page_token = None

    while True:
        if page_token:
            params['pageToken'] = page_token

        result = service.events().list(**params).execute()
        events.extend(result.get('items', []))

        page_token = result.get('nextPageToken')
        if not page_token or (max_results and len(events) >= max_results):
            break

    if max_results:
        events = events[:max_results]

    return events


def get_event(service, cal_id, event_id):
    """Get a single event by ID."""
    return service.events().get(calendarId=cal_id, eventId=event_id).execute()


def create_event(service, cal_id, event_body):
    """Create an event."""
    return service.events().insert(calendarId=cal_id, body=event_body).execute()


def update_event(service, cal_id, event_id, event_body):
    """Update an event."""
    return service.events().patch(
        calendarId=cal_id, eventId=event_id, body=event_body).execute()


def delete_event(service, cal_id, event_id, send_updates='none'):
    """Delete an event."""
    return service.events().delete(
        calendarId=cal_id, eventId=event_id, sendUpdates=send_updates).execute()


def build_event_body(args, existing_event=None):
    """Build event body from args."""
    body = {}

    if hasattr(args, 'summary') and args.summary:
        body['summary'] = args.summary

    if hasattr(args, 'location') and args.location:
        body['location'] = args.location

    if hasattr(args, 'description') and args.description:
        body['description'] = args.description

    # Handle start/end
    timezone = getattr(args, 'timezone', None) or DEFAULT_TIMEZONE
    all_day = getattr(args, 'all_day', False)

    if hasattr(args, 'start') and args.start:
        dt, is_date = parse_datetime(args.start, timezone)
        if dt:
            if all_day or is_date:
                body['start'] = {'date': dt if is_date else dt[:10]}
            else:
                body['start'] = {'dateTime': dt, 'timeZone': timezone}

    if hasattr(args, 'end') and args.end:
        dt, is_date = parse_datetime(args.end, timezone)
        if dt:
            if all_day or is_date:
                body['end'] = {'date': dt if is_date else dt[:10]}
            else:
                body['end'] = {'dateTime': dt, 'timeZone': timezone}

    # Color
    if hasattr(args, 'color') and args.color:
        color_id = parse_color(args.color)
        if color_id:
            body['colorId'] = color_id
        else:
            print(f"Couleur invalide: {args.color}")
            print("Couleurs disponibles:")
            for name, cid in COLORS.items():
                print(f"  {cid}: {name} ({COLOR_HEX[cid]})")
            sys.exit(1)

    # Status
    if hasattr(args, 'status') and args.status:
        if args.status in ('confirmed', 'tentative', 'cancelled'):
            body['status'] = args.status
        else:
            print(f"Statut invalide: {args.status}")
            print("Valeurs valides: confirmed, tentative, cancelled")
            sys.exit(1)

    # Visibility
    if hasattr(args, 'visibility') and args.visibility:
        if args.visibility in ('default', 'public', 'private', 'confidential'):
            body['visibility'] = args.visibility
        else:
            print(f"Visibilité invalide: {args.visibility}")
            print("Valeurs valides: default, public, private, confidential")
            sys.exit(1)

    # Transparency
    if hasattr(args, 'transparency') and args.transparency:
        if args.transparency in ('opaque', 'transparent'):
            body['transparency'] = args.transparency
        else:
            print(f"Transparence invalide: {args.transparency}")
            print("Valeurs valides: opaque, transparent")
            sys.exit(1)

    # Recurrence
    if hasattr(args, 'recurrence') and args.recurrence:
        body['recurrence'] = [args.recurrence]

    # Reminders for create
    if hasattr(args, 'reminder') and args.reminder:
        body['reminders'] = {
            'useDefault': False,
            'overrides': [{'method': 'popup', 'minutes': m} for m in args.reminder]
        }

    # Reminders for update
    if hasattr(args, 'remove_reminders') and args.remove_reminders:
        body['reminders'] = {'useDefault': True}
    elif hasattr(args, 'add_reminder') and args.add_reminder:
        # Get existing reminders
        current_reminders = []
        if existing_event:
            reminders = existing_event.get('reminders', {})
            if reminders.get('overrides'):
                current_reminders = reminders['overrides']

        # Add new reminders
        for minutes in args.add_reminder:
            current_reminders.append({'method': 'popup', 'minutes': minutes})

        body['reminders'] = {
            'useDefault': False,
            'overrides': current_reminders
        }

    # Attendees for create
    if hasattr(args, 'attendee') and args.attendee:
        body['attendees'] = [{'email': email} for email in args.attendee]

    # Attendees for update
    if existing_event and (
        (hasattr(args, 'add_attendee') and args.add_attendee) or
        (hasattr(args, 'remove_attendee') and args.remove_attendee)
    ):
        current_attendees = existing_event.get('attendees', [])

        if hasattr(args, 'add_attendee') and args.add_attendee:
            existing_emails = {a['email'] for a in current_attendees}
            for email in args.add_attendee:
                if email not in existing_emails:
                    current_attendees.append({'email': email})

        if hasattr(args, 'remove_attendee') and args.remove_attendee:
            remove_set = set(args.remove_attendee)
            current_attendees = [a for a in current_attendees if a['email'] not in remove_set]

        body['attendees'] = current_attendees

    return body


# Command handlers

def cmd_list(args):
    """Handle list command."""
    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)
    cal_id = get_calendar_id(service, args.calendar)

    try:
        events = list_events(
            service, cal_id,
            time_min=args.from_date,
            time_max=args.to_date,
            query=args.query,
            max_results=args.max_results
        )

        if args.json:
            output_json(events)
        else:
            if not events:
                print("Aucun événement trouvé")
                return

            print(f"Événements ({len(events)}):\n")
            for event in events:
                print(format_event_display(event))
                print()

    except HttpError as e:
        print(f"Erreur API: {e.reason}")
        sys.exit(1)


def cmd_show(args):
    """Handle show command."""
    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)
    cal_id = get_calendar_id(service, args.calendar)

    try:
        event = get_event(service, cal_id, args.event_id)

        if args.json:
            output_json(event)
        else:
            print(format_event_display(event, verbose=True))

    except HttpError as e:
        if e.resp.status == 404:
            print(f"Événement '{args.event_id}' introuvable")
        else:
            print(f"Erreur API: {e.reason}")
        sys.exit(1)


def cmd_create(args):
    """Handle create command."""
    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)
    cal_id = get_calendar_id(service, args.calendar)

    # Validate required fields
    if not args.summary:
        print("Erreur: --summary (-s) est requis")
        sys.exit(1)

    if not args.start or not args.end:
        print("Erreur: --start et --end sont requis")
        print("Formats valides: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD HH:MM")
        sys.exit(1)

    body = build_event_body(args)

    try:
        event = create_event(service, cal_id, body)

        if args.json:
            output_json(event)
        else:
            print("Événement créé:")
            print(format_event_display(event, verbose=True))

    except HttpError as e:
        print(f"Erreur API: {e.reason}")
        sys.exit(1)


def cmd_update(args):
    """Handle update command."""
    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)
    cal_id = get_calendar_id(service, args.calendar)

    try:
        # Get existing event for merge operations
        existing_event = get_event(service, cal_id, args.event_id)

        body = build_event_body(args, existing_event)

        if not body:
            print("Aucune modification spécifiée")
            sys.exit(1)

        event = update_event(service, cal_id, args.event_id, body)

        if args.json:
            output_json(event)
        else:
            print("Événement modifié:")
            print(format_event_display(event, verbose=True))

    except HttpError as e:
        if e.resp.status == 404:
            print(f"Événement '{args.event_id}' introuvable")
        else:
            print(f"Erreur API: {e.reason}")
        sys.exit(1)


def cmd_delete(args):
    """Handle delete command."""
    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)
    cal_id = get_calendar_id(service, args.calendar)

    try:
        # Check event exists
        event = get_event(service, cal_id, args.event_id)
        summary = event.get('summary', '(sans titre)')

        if not args.yes:
            response = input(f"Supprimer '{summary}' ? (o/N) ")
            if response.lower() not in ('o', 'oui', 'y', 'yes'):
                print("Annulé")
                return

        delete_event(service, cal_id, args.event_id, args.send_updates)
        print(f"Événement '{summary}' supprimé")

    except HttpError as e:
        if e.resp.status == 404:
            print(f"Événement '{args.event_id}' introuvable")
        else:
            print(f"Erreur API: {e.reason}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="CRUD operations for Google Calendar events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list
  %(prog)s list -c "Work" --from 2026-03-01 --to 2026-03-31
  %(prog)s show abc123xyz
  %(prog)s create -s "Meeting" --start 2026-03-15T14:00 --end 2026-03-15T15:00
  %(prog)s create -s "Holiday" --start 2026-03-25 --end 2026-03-26 --all-day
  %(prog)s update abc123xyz --color tomato -l "Room A"
  %(prog)s delete abc123xyz -y

Colors: lavender, sage, grape, flamingo, banana, tangerine, peacock, graphite, blueberry, basil, tomato
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # list command
    list_parser = subparsers.add_parser('list', help='List events')
    list_parser.add_argument('-c', '--calendar', help='Calendar name or ID (default: primary)')
    list_parser.add_argument('--from', dest='from_date', metavar='DATE',
                             help='Start date (YYYY-MM-DD)')
    list_parser.add_argument('--to', dest='to_date', metavar='DATE',
                             help='End date (YYYY-MM-DD)')
    list_parser.add_argument('-q', '--query', help='Search text')
    list_parser.add_argument('-n', '--max-results', type=int, metavar='MAX',
                             help='Maximum number of events')
    list_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # show command
    show_parser = subparsers.add_parser('show', help='Show event details')
    show_parser.add_argument('event_id', help='Event ID')
    show_parser.add_argument('-c', '--calendar', help='Calendar name or ID (default: primary)')
    show_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # create command
    create_parser = subparsers.add_parser('create', help='Create an event')
    create_parser.add_argument('-s', '--summary', required=True, help='Event title')
    create_parser.add_argument('--start', required=True, help='Start date/time')
    create_parser.add_argument('--end', required=True, help='End date/time')
    create_parser.add_argument('-c', '--calendar', help='Calendar name or ID (default: primary)')
    create_parser.add_argument('-l', '--location', help='Location')
    create_parser.add_argument('-d', '--description', help='Description')
    create_parser.add_argument('--color', help='Color (name or 1-11)')
    create_parser.add_argument('--all-day', action='store_true', help='All-day event')
    create_parser.add_argument('--timezone', default=DEFAULT_TIMEZONE, help='Timezone')
    create_parser.add_argument('--recurrence', help='Recurrence rule (RRULE)')
    create_parser.add_argument('--visibility', choices=['default', 'public', 'private', 'confidential'],
                               help='Event visibility')
    create_parser.add_argument('--transparency', choices=['opaque', 'transparent'],
                               help='Show as busy (opaque) or free (transparent)')
    create_parser.add_argument('--reminder', type=int, action='append', metavar='MINUTES',
                               help='Reminder in minutes (can be repeated)')
    create_parser.add_argument('--attendee', action='append', metavar='EMAIL',
                               help='Attendee email (can be repeated)')
    create_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # update command
    update_parser = subparsers.add_parser('update', help='Update an event')
    update_parser.add_argument('event_id', help='Event ID')
    update_parser.add_argument('-c', '--calendar', help='Calendar name or ID (default: primary)')
    update_parser.add_argument('-s', '--summary', help='Event title')
    update_parser.add_argument('--start', help='Start date/time')
    update_parser.add_argument('--end', help='End date/time')
    update_parser.add_argument('-l', '--location', help='Location')
    update_parser.add_argument('-d', '--description', help='Description')
    update_parser.add_argument('--color', help='Color (name or 1-11)')
    update_parser.add_argument('--timezone', default=DEFAULT_TIMEZONE, help='Timezone')
    update_parser.add_argument('--status', choices=['confirmed', 'tentative', 'cancelled'],
                               help='Event status')
    update_parser.add_argument('--visibility', choices=['default', 'public', 'private', 'confidential'],
                               help='Event visibility')
    update_parser.add_argument('--transparency', choices=['opaque', 'transparent'],
                               help='Show as busy (opaque) or free (transparent)')
    update_parser.add_argument('--add-reminder', type=int, action='append', metavar='MINUTES',
                               help='Add reminder in minutes')
    update_parser.add_argument('--remove-reminders', action='store_true',
                               help='Remove all custom reminders')
    update_parser.add_argument('--add-attendee', action='append', metavar='EMAIL',
                               help='Add attendee email')
    update_parser.add_argument('--remove-attendee', action='append', metavar='EMAIL',
                               help='Remove attendee email')
    update_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # delete command
    delete_parser = subparsers.add_parser('delete', help='Delete an event')
    delete_parser.add_argument('event_id', help='Event ID')
    delete_parser.add_argument('-c', '--calendar', help='Calendar name or ID (default: primary)')
    delete_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')
    delete_parser.add_argument('--send-updates', choices=['all', 'externalOnly', 'none'],
                               default='none', help='Send cancellation notifications')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        'list': cmd_list,
        'show': cmd_show,
        'create': cmd_create,
        'update': cmd_update,
        'delete': cmd_delete,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
