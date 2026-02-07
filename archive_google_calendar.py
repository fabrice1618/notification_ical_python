#!/usr/bin/env python3
"""
Archive un calendrier Google en transférant ses événements vers un calendrier archive.
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pickle
import os
import argparse

SCOPES = ['https://www.googleapis.com/auth/calendar']


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


def get_calendar_events(service, cal_id):
    """Récupère tous les événements d'un calendrier."""
    events = []
    page_token = None

    while True:
        result = service.events().list(
            calendarId=cal_id,
            singleEvents=False,
            pageToken=page_token
        ).execute()

        events.extend(result.get('items', []))
        page_token = result.get('nextPageToken')

        if not page_token:
            break

    return events


def get_event_signature(event):
    """Génère une signature unique pour un événement (title, start, end)."""
    title = event.get('summary', '')
    start = event.get('start', {})
    end = event.get('end', {})

    # start/end peuvent être dateTime ou date
    start_str = start.get('dateTime') or start.get('date') or ''
    end_str = end.get('dateTime') or end.get('date') or ''

    return (title, start_str, end_str)


def load_archive_signatures(service, archive_id):
    """Charge les signatures de tous les événements de l'archive."""
    events = get_calendar_events(service, archive_id)
    return {get_event_signature(event) for event in events}


def copy_event(service, event, dest_cal_id):
    """Copie un événement vers un calendrier destination."""
    # Champs à copier
    new_event = {
        'summary': event.get('summary', ''),
        'location': event.get('location', ''),
        'description': event.get('description', ''),
        'start': event.get('start'),
        'end': event.get('end'),
        'recurrence': event.get('recurrence'),
        'reminders': event.get('reminders'),
    }

    # Supprimer les clés None
    new_event = {k: v for k, v in new_event.items() if v is not None}

    return service.events().insert(calendarId=dest_cal_id, body=new_event).execute()


def archive_calendar(source_name, archive_name, dry_run=False, resume=False):
    """Archive un calendrier en transférant ses événements."""
    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)

    # Trouver le calendrier source
    source_cal = find_calendar(service, source_name)
    if not source_cal:
        print(f"Erreur: Calendrier source '{source_name}' introuvable")
        return False

    source_id = source_cal['id']
    source_display = source_cal.get('summary', source_id)

    # Trouver le calendrier archive
    archive_cal = find_calendar(service, archive_name)
    if not archive_cal:
        print(f"Erreur: Calendrier archive '{archive_name}' introuvable")
        return False

    archive_id = archive_cal['id']
    archive_display = archive_cal.get('summary', archive_id)

    # Vérifier qu'on n'archive pas vers lui-même
    if source_id == archive_id:
        print("Erreur: Source et archive sont le même calendrier")
        return False

    print(f"Source:  {source_display}")
    print(f"Archive: {archive_display}")

    # Charger les signatures de l'archive si mode resume
    archive_signatures = set()
    if resume:
        print("Chargement des événements de l'archive...")
        archive_signatures = load_archive_signatures(service, archive_id)
        print(f"Événements déjà archivés: {len(archive_signatures)}")

    # Récupérer les événements
    events = get_calendar_events(service, source_id)
    print(f"Événements à transférer: {len(events)}")

    if not events:
        print("Aucun événement à archiver")
        return True

    if dry_run:
        print("\n[DRY-RUN] Aucune modification effectuée")
        return True

    # Transférer les événements
    print("\nTransfert en cours...")
    success_count = 0
    skipped_count = 0
    error_count = 0

    for event in events:
        title = event.get('summary', '(sans titre)')

        # Vérifier si l'événement existe déjà dans l'archive (mode resume)
        if resume and get_event_signature(event) in archive_signatures:
            skipped_count += 1
            print(f"  = {title} (déjà présent)")
            continue

        try:
            copy_event(service, event, archive_id)
            success_count += 1
            print(f"  + {title}")
        except Exception as e:
            error_count += 1
            print(f"  ! {title} - Erreur: {e}")

    print(f"\nTransférés: {success_count}, Ignorés: {skipped_count}, Erreurs: {error_count}")

    # Supprimer le calendrier source si tout s'est bien passé
    if error_count == 0:
        print(f"\nSuppression du calendrier source '{source_display}'...")
        try:
            # calendars().delete() pour supprimer un calendrier dont on est propriétaire
            # calendarList().delete() ne fait que désabonner
            service.calendars().delete(calendarId=source_id).execute()
            print("Calendrier source supprimé")
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression: {e}")
            return False
    else:
        print(f"\n{error_count} erreur(s) - Calendrier source non supprimé")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Archive un calendrier Google vers un calendrier archive"
    )
    parser.add_argument(
        'source',
        help="Nom ou ID du calendrier à archiver"
    )
    parser.add_argument(
        '-a', '--archive',
        required=True,
        help="Nom ou ID du calendrier archive destination"
    )
    parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help="Simuler sans effectuer de modifications"
    )
    parser.add_argument(
        '-r', '--resume',
        action='store_true',
        help="Reprendre un archivage interrompu (ignore les événements déjà présents)"
    )

    args = parser.parse_args()

    success = archive_calendar(args.source, args.archive, dry_run=args.dry_run, resume=args.resume)
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
