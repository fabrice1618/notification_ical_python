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


def display_comparison_event(item: dict, prefix: str):
    """Affiche un événement de comparaison (modified/missing/extra)"""
    event = item.get('event', {})
    title = event.get('title', '(sans titre)')
    start = event.get('start', '')
    location = event.get('location', '')
    loc_str = f" @ {location}" if location else ""
    print(f"{prefix}{start} | {title}{loc_str}")


def display_comparison_details(details: dict):
    """Affiche le détail des différences d'une comparaison"""
    modified = details.get('modified', [])
    missing = details.get('missing', [])
    extra = details.get('extra', [])

    if not modified and not missing and not extra:
        return

    if modified:
        print(f"\n    DIFFÉRENCES ({len(modified)})")
        for item in modified:
            ref = item.get('ref_event', {})
            prop = item.get('prop_event', {})
            start = item.get('start', '')
            ref_title = ref.get('title', '(sans titre)')
            ref_loc = ref.get('location', '')
            prop_title = prop.get('title', '(sans titre)')
            prop_loc = prop.get('location', '')
            print(f"      ~ {start} |")
            print(f"          Réf:  {ref_title} @ {ref_loc}")
            print(f"          Prop: {prop_title} @ {prop_loc}")
            for diff in item.get('differences', []):
                field = diff.get('field', '')
                ref_val = diff.get('ref', '')
                prop_val = diff.get('prop', '')
                print(f"          {field}: {ref_val} → {prop_val}")

    if missing:
        print(f"\n    MANQUANTS ({len(missing)})")
        for item in missing:
            display_comparison_event(item, "      - ")

    if extra:
        print(f"\n    EXTRA ({len(extra)})")
        for item in extra:
            display_comparison_event(item, "      + ")


def display_result(data: dict, filepath: str):
    """Affiche le résultat complet"""
    config = data.get('config', {})

    print(f"\nFichier: {os.path.basename(filepath)}")
    if config.get('dry_run'):
        print(f"Mode: dry-run")

    for source_name, source_data in data.get('sources', {}).items():
        events = source_data.get('events_count', 0)
        changes = source_data.get('changes_count', 0)

        print(f"\n[{source_name}] {events} événements, {changes} changements")

        date_debut = source_data.get('date_debut')
        date_fin = source_data.get('date_fin')
        if date_debut or date_fin:
            print(f"  Période: {date_debut or '...'} → {date_fin or '...'}")

        if source_data.get('status') == 'error':
            print(f"  ERREUR: {source_data.get('error_type')}: {source_data.get('error_message')}")
        elif changes > 0:
            display_changes(source_data.get('changes', []))

    # Section comparaisons
    comparisons = data.get('comparisons', {})
    if comparisons:
        print(f"\n{'='*50}")
        print("COMPARAISONS")
        for comp_name, comp in comparisons.items():
            print(f"\n  [{comp['ref_source']} vs {comp['prop_source']}]")
            if comp['status'] == 'error':
                print(f"    ERREUR: {comp.get('error_message')}")
            elif comp['status'] == 'skipped':
                print(f"    IGNORÉ: {comp.get('reason')}")
            else:
                total = comp['matches_count'] + comp['modified_count'] + comp['missing_count']
                pct = (comp['matches_count'] / total * 100) if total > 0 else 0
                print(f"    Correspondances: {comp['matches_count']}/{total} ({pct:.0f}%)")
                print(f"    Différences: {comp['modified_count']}")
                print(f"    Manquants: {comp['missing_count']}")
                print(f"    Extra: {comp['extra_count']}")
                display_comparison_details(comp.get('details', {}))


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
