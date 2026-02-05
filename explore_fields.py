#!/usr/bin/env python3
"""
Script d'exploration des champs disponibles dans les calendriers iCal.

Analyse les sources configurées et liste tous les champs présents
dans les événements pour identifier les données exploitables.
"""

import requests
from urllib3.exceptions import InsecureRequestWarning
from icalendar import Calendar
import json
import warnings
from collections import defaultdict
from typing import Any


def load_sources(config_file: str = "sources.json") -> dict[str, Any]:
    """Charge la configuration des sources"""
    with open(config_file, 'r', encoding='utf-8') as f:
        result: dict[str, Any] = json.load(f)
        return result


def fetch_calendar(url: str, verify_ssl: bool = True) -> Any:
    """Télécharge et parse un calendrier iCal"""
    # Normaliser webcal:// vers https://
    url = url.replace("webcal://", "https://")

    if not verify_ssl:
        warnings.filterwarnings('ignore', category=InsecureRequestWarning)

    response = requests.get(url, timeout=30, verify=verify_ssl)
    response.raise_for_status()
    return Calendar.from_ical(response.text)


def analyze_calendar(cal: Any) -> dict[str, Any]:
    """
    Analyse un calendrier et retourne les statistiques des champs.

    Returns:
        Dict avec:
        - fields: dict des champs et leur nombre d'occurrences
        - samples: dict des champs avec des exemples de valeurs
        - event_count: nombre total d'événements
    """
    fields_count: defaultdict[str, int] = defaultdict(int)
    fields_samples: defaultdict[str, list[str]] = defaultdict(list)
    event_count = 0

    for component in cal.walk():
        if component.name == "VEVENT":
            event_count += 1

            for prop_name in component.keys():
                fields_count[prop_name] += 1

                # Garder quelques exemples (max 3)
                if len(fields_samples[prop_name]) < 3:
                    value = component.get(prop_name)
                    # Convertir en string pour l'affichage
                    try:
                        if hasattr(value, 'dt'):
                            sample = str(value.dt)
                        else:
                            sample = str(value)[:100]  # Limiter la longueur
                    except Exception:
                        sample = "<non convertible>"

                    if sample not in fields_samples[prop_name]:
                        fields_samples[prop_name].append(sample)

    return {
        'fields': dict(fields_count),
        'samples': dict(fields_samples),
        'event_count': event_count
    }


def print_analysis(source_name: str, analysis: dict[str, Any]) -> None:
    """Affiche l'analyse d'une source de manière lisible"""
    print(f"\n{'='*70}")
    print(f"SOURCE: {source_name}")
    print(f"{'='*70}")
    print(f"Nombre d'événements: {analysis['event_count']}")
    print(f"\nChamps trouvés ({len(analysis['fields'])}):")
    print("-" * 70)

    # Trier par fréquence décroissante
    sorted_fields = sorted(
        analysis['fields'].items(),
        key=lambda x: x[1],
        reverse=True
    )

    for field, count in sorted_fields:
        pct = (count / analysis['event_count'] * 100) if analysis['event_count'] > 0 else 0
        samples = analysis['samples'].get(field, [])
        sample_str = samples[0] if samples else ""

        # Tronquer l'exemple si trop long
        if len(sample_str) > 40:
            sample_str = sample_str[:37] + "..."

        print(f"  {field:<25} {count:>5} ({pct:>5.1f}%)  ex: {sample_str}")


def main() -> None:
    """Point d'entrée principal"""
    print("Exploration des champs iCal disponibles")
    print("=" * 70)

    # Charger les sources
    try:
        sources = load_sources()
    except FileNotFoundError:
        print("ERREUR: Fichier sources.json introuvable")
        return
    except json.JSONDecodeError as e:
        print(f"ERREUR: Format JSON invalide dans sources.json: {e}")
        return

    print(f"Sources configurées: {', '.join(sources.keys())}")

    all_fields: set[str] = set()
    results: dict[str, Any] = {}

    # Analyser chaque source
    for source_name, config in sources.items():
        print(f"\nAnalyse de '{source_name}'...")

        try:
            verify_ssl = config.get('verify_ssl', True)
            cal = fetch_calendar(config['url'], verify_ssl)
            analysis = analyze_calendar(cal)
            results[source_name] = analysis
            all_fields.update(analysis['fields'].keys())
            print_analysis(source_name, analysis)

        except requests.exceptions.RequestException as e:
            print(f"  ERREUR de connexion: {e}")
            results[source_name] = {'error': str(e)}

        except Exception as e:
            print(f"  ERREUR: {e}")
            results[source_name] = {'error': str(e)}

    # Résumé comparatif
    print(f"\n{'='*70}")
    print("RESUME COMPARATIF")
    print(f"{'='*70}")
    print(f"\nTous les champs uniques trouvés ({len(all_fields)}):")

    for field in sorted(all_fields):
        presence: list[str] = []
        for source_name, analysis in results.items():
            if 'fields' in analysis and field in analysis['fields']:
                presence.append(source_name)
        print(f"  {field:<25} -> {', '.join(presence)}")

    # Champs actuellement utilisés vs disponibles
    used_fields: set[str] = {'UID', 'SUMMARY', 'LOCATION', 'DTSTART', 'DTEND', 'DESCRIPTION', 'DTSTAMP', 'STATUS'}
    unused_fields: set[str] = all_fields - used_fields

    print(f"\n{'='*70}")
    print("CHAMPS ACTUELLEMENT UTILISES")
    print(f"{'='*70}")
    for field in sorted(used_fields):
        status = "OK" if field in all_fields else "NON TROUVE"
        print(f"  {field:<25} [{status}]")

    if unused_fields:
        print(f"\n{'='*70}")
        print("CHAMPS DISPONIBLES NON EXPLOITES")
        print(f"{'='*70}")
        for field in sorted(unused_fields):
            print(f"  {field}")


if __name__ == "__main__":
    main()
