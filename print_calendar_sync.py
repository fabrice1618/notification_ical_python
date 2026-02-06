#!/usr/bin/env python3
"""
Affiche le contenu d'un fichier de résultat calendar_sync.
"""

import argparse
import json
import os
import glob

DATA_SYNC_DIR = "data_sync"


def find_latest_result_file() -> str:
    """Trouve le fichier calendar_sync le plus récent"""
    pattern = os.path.join(DATA_SYNC_DIR, "*_calendar_sync.json")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Aucun fichier *_calendar_sync.json trouvé dans {DATA_SYNC_DIR}/")
    return max(files)


def load_result(filepath: str) -> dict:
    """Charge un fichier de résultat JSON"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def display_event(event: dict, prefix: str = ""):
    """Affiche les infos d'un événement"""
    title = event.get('title', '(sans titre)')
    start = event.get('start', '')
    location = event.get('location', '')

    print(f"{prefix}{title}")
    print(f"{prefix}  Date: {start}")
    if location:
        print(f"{prefix}  Lieu: {location}")


def display_changes(changes: list):
    """Affiche les changements groupés par type"""
    if not changes:
        return

    new_events = [c for c in changes if c['type'] == 'new_event']
    modified_events = [c for c in changes if c['type'] == 'modified_event']
    deleted_events = [c for c in changes if c['type'] == 'deleted_event']

    if new_events:
        print(f"\n  NOUVEAUX ({len(new_events)})")
        for item in new_events:
            event = item['event']
            title = event.get('title', '(sans titre)')
            start = event.get('start', '')
            location = event.get('location', '')
            loc_str = f" @ {location}" if location else ""
            print(f"    + {start} | {title}{loc_str}")

    if modified_events:
        print(f"\n  MODIFIÉS ({len(modified_events)})")
        for item in modified_events:
            event = item['event']
            title = event.get('title', '(sans titre)')
            start = event.get('start', '')
            print(f"    ~ {start} | {title}")
            for ch in item.get('changes', []):
                print(f"        {ch['field']}: {ch['old_value']} → {ch['new_value']}")

    if deleted_events:
        print(f"\n  SUPPRIMÉS ({len(deleted_events)})")
        for item in deleted_events:
            event = item['event']
            title = event.get('title', '(sans titre)')
            start = event.get('start', '')
            print(f"    - {start} | {title}")


def display_result(data: dict, filepath: str):
    """Affiche le résultat complet"""
    config = data.get('config', {})

    print(f"\nFichier: {os.path.basename(filepath)}")
    print(f"Période: {config.get('date_debut')} → {config.get('date_fin')}")
    if config.get('dry_run'):
        print(f"Mode: dry-run")

    for source_name, source_data in data.get('sources', {}).items():
        events = source_data.get('events_count', 0)
        changes = source_data.get('changes_count', 0)

        print(f"\n[{source_name}] {events} événements, {changes} changements")

        if source_data.get('status') == 'error':
            print(f"  ERREUR: {source_data.get('error_type')}: {source_data.get('error_message')}")
        elif changes > 0:
            display_changes(source_data.get('changes', []))


def main():
    parser = argparse.ArgumentParser(
        description="Affiche le résultat d'une synchronisation calendar_sync"
    )
    parser.add_argument(
        '-f', '--file',
        help="Fichier à afficher (par défaut: le plus récent)"
    )

    args = parser.parse_args()

    try:
        if args.file:
            filepath = args.file
        else:
            filepath = find_latest_result_file()

        data = load_result(filepath)
        display_result(data, filepath)

    except FileNotFoundError as e:
        print(f"Erreur: {e}")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Erreur de lecture JSON: {e}")
        exit(1)


if __name__ == "__main__":
    main()
