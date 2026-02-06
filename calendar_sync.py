"""
Système de synchronisation de calendrier iCal multi-sources.

Ce script télécharge des calendriers iCal, détecte les changements
et génère des notifications horodatées pour informer des modifications.
"""

import requests
from urllib3.exceptions import InsecureRequestWarning
from icalendar import Calendar, Component
import json
import logging
import argparse
from datetime import datetime
import os
from urllib.parse import urlparse
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import warnings

# =============================================================================
# CONSTANTES DE CONFIGURATION
# =============================================================================

# Noms des champs
FIELD_UID = 'uid'
FIELD_TITLE = 'title'
FIELD_LOCATION = 'location'
FIELD_START = 'start'
FIELD_END = 'end'
FIELD_DESCRIPTION = 'description'
FIELD_LAST_MODIFIED = 'last_modified'
FIELD_DTSTAMP = 'dtstamp'
FIELD_STATUS = 'status'

# Configuration réseau
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

# Fichiers et dossiers
CONFIG_FILE = "sources.json"
DATA_DIR = "data"
NOTIFICATIONS_DIR = "notifications"
LOG_FILE = os.path.join(DATA_DIR, "calendar_sync.log")

# Format de date pour la date limite
DATE_FORMAT = "%Y-%m-%d"

# Plage de dates globale pour le filtrage des événements
DATE_DEBUT = "2025-08-01"
DATE_FIN = "2026-07-31"

# Horodatage unique pour tout le processus
NOW = datetime.now()

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(NOTIFICATIONS_DIR, exist_ok=True)

# =============================================================================
# CONFIGURATION DU LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMERATIONS
# =============================================================================

class ChangeType(Enum):
    """Types de changements détectables"""
    TITLE = "title_change"
    LOCATION = "location_change"
    START_TIME = "start_time_change"
    END_TIME = "end_time_change"
    DESCRIPTION = "description_change"
    STATUS = "status_change"
    NEW_EVENT = "new_event"
    MODIFIED_EVENT = "modified_event"
    DELETED_EVENT = "deleted_event"


# =============================================================================
# CLASSES DE DONNEES
# =============================================================================

@dataclass
class Change:
    """Représente un changement détecté"""
    type: str
    field: str
    old_value: Optional[str]
    new_value: Optional[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Event:
    """Représente un événement du calendrier"""
    uid: str
    title: str
    location: str
    start: str
    end: str
    description: str
    last_modified: str
    dtstamp: str
    status: str

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Event':
        return cls(**data)



# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def lire_json(filepath: str) -> Optional[Dict]:
    """Lit un fichier JSON et retourne son contenu, ou None si inexistant"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        if not content.strip():
            return None
        return json.loads(content)


def ecrire_json(filepath: str, data) -> str:
    """Écrit des données dans un fichier JSON"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return filepath


def save_notification(source: str, changes: List[Dict]):
    """Sauvegarde les changements dans un fichier notification horodaté."""
    timestamp = NOW.strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(NOTIFICATIONS_DIR, f"{timestamp}_notifications_{source}.json")
    ecrire_json(filepath, changes)
    logger.info(f"Notification sauvegardée: {filepath}")
    return filepath


def save_process(process_data: Dict):
    """Sauvegarde le compte-rendu du processus dans un fichier horodaté."""
    timestamp = NOW.strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(NOTIFICATIONS_DIR, f"{timestamp}_process.json")
    ecrire_json(filepath, process_data)
    logger.info(f"Processus sauvegardé: {filepath}")
    return filepath


# =============================================================================
# FILTRE PAR DATE
# =============================================================================

class DateFilter:
    """Filtre les événements selon la plage de dates globale [DATE_DEBUT, DATE_FIN]"""

    def __init__(self):
        self.date_debut = self._parse_date(DATE_DEBUT, "DATE_DEBUT")
        self.date_fin = self._parse_date(DATE_FIN, "DATE_FIN")

    @staticmethod
    def _parse_date(date_str: Optional[str], field_name: str) -> Optional[datetime]:
        """Parse une date de configuration si fournie"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, DATE_FORMAT)
        except ValueError:
            logger.warning(f"Format de {field_name} invalide: {date_str} (attendu: YYYY-MM-DD)")
            return None

    def is_in_range(self, start_iso: str) -> bool:
        """Indique si un événement dont la date de début est start_iso doit être conservé"""
        if not self.date_debut and not self.date_fin:
            return True

        if 'T' in start_iso:
            event_day = datetime.fromisoformat(start_iso.replace('Z', '+00:00')).date()
        else:
            event_day = datetime.strptime(start_iso, DATE_FORMAT).date()

        if self.date_debut and event_day < self.date_debut.date():
            return False

        if self.date_fin and event_day > self.date_fin.date():
            return False

        return True


# =============================================================================
# SOURCE
# =============================================================================

class Source:
    """Représente une source de calendrier configurée dans sources.json"""

    def __init__(self, name: str, url: str, description: str = '', verify_ssl: bool = True):
        """
        Args:
            name: Nom de la source (clé dans sources.json)
            url: URL du calendrier iCal (webcal:// ou https://)
            description: Description de la source
            verify_ssl: Vérifier le certificat SSL (défaut: True)
        """
        self.name = name
        self.url = self._validate_and_normalize_url(url)
        self.description = description
        self.date_filter = DateFilter()
        self.verify_ssl = verify_ssl
        self.state_file = os.path.join(DATA_DIR, f"etat_{name}.json")

        if not verify_ssl:
            logger.warning(f"Vérification SSL désactivée pour {name}")
            warnings.filterwarnings('ignore', category=InsecureRequestWarning)

    @classmethod
    def load_all_configs(cls, config_file: str = CONFIG_FILE) -> List['Source']:
        """Charge toutes les sources depuis le fichier de configuration"""
        sources = lire_json(config_file)
        if sources is None:
            raise FileNotFoundError(f"Fichier de configuration introuvable ou vide: {config_file}")

        return [
            cls(
                name=name,
                url=config['url'],
                description=config.get('description', ''),
                verify_ssl=config.get('verify_ssl', True)
            )
            for name, config in sources.items()
        ]

    @staticmethod
    def _validate_and_normalize_url(url: str) -> str:
        """Valide et normalise l'URL du calendrier"""
        normalized_url = url.replace("webcal://", "https://")

        try:
            parsed = urlparse(normalized_url)
        except Exception:
            raise ValueError(f"URL invalide: {url}")

        if parsed.scheme not in ('http', 'https'):
            raise ValueError(f"Schéma d'URL non supporté: {parsed.scheme}")

        if not parsed.netloc:
            raise ValueError(f"URL sans hôte: {url}")

        return normalized_url


# =============================================================================
# CALENDRIER SOURCE
# =============================================================================

class CalendarSource:
    """Télécharge et parse un calendrier iCal avec filtrage par date"""

    def __init__(self, source: Source):
        """
        Args:
            source: Source de calendrier (URL, SSL, DateFilter)
        """
        self.source = source
        self.events: Dict[str, Dict] = {}

    def fetch(self):
        """Télécharge et parse le calendrier. Stocke le résultat dans self.events."""
        cal = self._download()
        self.events = self._parse(cal)

    def _download(self) -> Component:
        """Télécharge et parse le calendrier iCal avec retry"""
        import time

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(self.source.url, timeout=REQUEST_TIMEOUT, verify=self.source.verify_ssl)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                logger.warning(f"Échec du téléchargement (tentative {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    raise

        return Calendar.from_ical(response.text)

    def _parse(self, cal: Component) -> Dict[str, Dict]:
        """Parse les événements bruts du calendrier"""
        events = {}

        for component in cal.walk():
            if component.name == "VEVENT":
                uid = component.get('uid')

                if not uid:
                    logger.warning("Événement sans UID ignoré")
                    continue

                uid = str(uid).strip()
                if not uid:
                    logger.warning("Événement avec UID vide ignoré")
                    continue

                start_iso = component.get('dtstart').dt.isoformat()

                if not self.source.date_filter.is_in_range(start_iso):
                    continue

                event_data = {
                    FIELD_UID: uid,
                    FIELD_TITLE: str(component.get('summary', '') or ''),
                    FIELD_LOCATION: str(component.get('location', '') or ''),
                    FIELD_START: start_iso,
                    FIELD_END: component.get('dtend').dt.isoformat(),
                    FIELD_DESCRIPTION: str(component.get('description', '') or ''),
                    FIELD_LAST_MODIFIED: NOW.isoformat(),
                    FIELD_DTSTAMP: component.get('dtstamp').dt.isoformat() if component.get('dtstamp') else None,
                    FIELD_STATUS: str(component.get('status', '') or '')
                }

                events[uid] = event_data

        logger.info(f"{len(events)} événement(s) parsé(s)")
        return events


# =============================================================================
# CLASSE PRINCIPALE
# =============================================================================

class CalendarSync:
    """Classe principale de synchronisation du calendrier"""

    def __init__(self, source: Source, dry_run: bool = False):
        """
        Args:
            source: Source de calendrier à synchroniser
            dry_run: Si True, ne pas sauvegarder l'état (défaut: False)
        """
        self.source = source
        self.dry_run = dry_run

    @staticmethod
    def detect_changes(old_event: Dict, new_event: Dict) -> List[Change]:
        """Détecte tous les changements entre deux versions d'un événement"""
        changes = []

        if old_event.get(FIELD_TITLE) != new_event.get(FIELD_TITLE):
            changes.append(Change(
                type=ChangeType.TITLE.value,
                field="Titre",
                old_value=old_event.get(FIELD_TITLE),
                new_value=new_event.get(FIELD_TITLE),
            ))

        if old_event.get(FIELD_LOCATION) != new_event.get(FIELD_LOCATION):
            changes.append(Change(
                type=ChangeType.LOCATION.value,
                field="Salle",
                old_value=old_event.get(FIELD_LOCATION),
                new_value=new_event.get(FIELD_LOCATION),
            ))

        if old_event.get(FIELD_DESCRIPTION) != new_event.get(FIELD_DESCRIPTION):
            changes.append(Change(
                type=ChangeType.DESCRIPTION.value,
                field="Description",
                old_value=old_event.get(FIELD_DESCRIPTION),
                new_value=new_event.get(FIELD_DESCRIPTION),
            ))

        if old_event.get(FIELD_STATUS) != new_event.get(FIELD_STATUS):
            changes.append(Change(
                type=ChangeType.STATUS.value,
                field="Statut",
                old_value=old_event.get(FIELD_STATUS),
                new_value=new_event.get(FIELD_STATUS),
            ))

        if old_event.get(FIELD_START) != new_event.get(FIELD_START):
            changes.append(Change(
                type=ChangeType.START_TIME.value,
                field="Date/Heure de début",
                old_value=old_event.get(FIELD_START),
                new_value=new_event.get(FIELD_START),
            ))

        if old_event.get(FIELD_END) != new_event.get(FIELD_END):
            changes.append(Change(
                type=ChangeType.END_TIME.value,
                field="Date/Heure de fin",
                old_value=old_event.get(FIELD_END),
                new_value=new_event.get(FIELD_END),
            ))

        return changes

    def load_state(self) -> Dict[str, Dict]:
        """Charge l'état depuis le fichier JSON"""
        state = lire_json(self.source.state_file)
        if state is None:
            logger.info(f"Fichier d'état inexistant ou vide: {self.source.state_file}")
            return {}
        return state

    def save_state(self, events: Dict[str, Dict]):
        """Sauvegarde l'état dans le fichier JSON de manière atomique"""
        ecrire_json(self.source.state_file, events)
        logger.debug(f"État sauvegardé dans {self.source.state_file}")

    def detect_all_changes(self, old_state: Dict, new_state: Dict) -> List[Dict]:
        """
        Détecte tous les changements entre l'ancien et le nouvel état

        Returns:
            Liste des changements détectés avec toutes les informations
        """
        changes_list = []

        for uid, new_event in new_state.items():
            if uid in old_state:
                old_event = old_state[uid]
                changes = self.detect_changes(old_event, new_event)

                if changes:
                    changes_list.append({
                        'type': ChangeType.MODIFIED_EVENT.value,
                        'event': new_event,
                        'previous': old_event,
                        'changes': [change.to_dict() for change in changes],
                    })
                    logger.info(f"Événement modifié: {uid}")
            else:
                changes_list.append({
                    'type': ChangeType.NEW_EVENT.value,
                    'event': new_event,
                })
                logger.info(f"Nouvel événement: {uid}")

        for uid in set(old_state.keys()) - set(new_state.keys()):
            changes_list.append({
                'type': ChangeType.DELETED_EVENT.value,
                'event': old_state[uid],
            })
            logger.info(f"Événement supprimé: {uid}")

        return changes_list

    def process(self) -> Dict:
        """
        Processus principal de synchronisation

        Returns:
            Dictionnaire avec les résultats de la synchronisation
        """
        logger.info("=" * 60)
        logger.info(f"SYNCHRONISATION - Source: {self.source.name}")
        logger.info("=" * 60)

        # Étape 1 : Charger l'état actuel (déjà filtré)
        logger.info(f"Chargement de {self.source.state_file}...")
        old_state = self.load_state()
        logger.info(f"{len(old_state)} événement(s) dans l'état actuel")

        # Étape 2 : Télécharger, parser et filtrer le calendrier
        calendar_source = CalendarSource(self.source)
        calendar_source.fetch()
        new_state = calendar_source.events

        # Étape 3 : Détecter les changements
        logger.info("Détection des changements...")
        changes = self.detect_all_changes(old_state, new_state)

        if changes:
            logger.info(f"{len(changes)} changement(s) détecté(s)")
        else:
            logger.info("Aucun changement détecté")

        # Étape 4 : Remplacer l'ancien état par le nouveau
        if self.dry_run:
            logger.info("Mode dry-run : état non sauvegardé")
        else:
            logger.info(f"Mise à jour de {self.source.state_file}...")
            self.save_state(new_state)

        logger.info("=" * 60)
        logger.info("SYNCHRONISATION TERMINÉE")
        logger.info("=" * 60)

        return {
            'status': 'success',
            'timestamp': NOW.isoformat(),
            'events_count': len(new_state),
            'changes': changes
        }


# =============================================================================
# AFFICHAGE
# =============================================================================

def display_changes(source_name: str, changes: List[Dict]):
    """Affiche les changements d'une source de manière lisible"""
    if not changes:
        print(f"\n  Aucun changement détecté")
        return

    print(f"\n  {len(changes)} changement(s) :")
    for i, item in enumerate(changes, 1):
        event = item['event']
        change_type = item['type']
        title = event.get(FIELD_TITLE, '(sans titre)')

        if change_type == ChangeType.NEW_EVENT.value:
            print(f"  [{i}] + {title}")
            print(f"      Date: {event.get(FIELD_START)}")

        elif change_type == ChangeType.MODIFIED_EVENT.value:
            print(f"  [{i}] ~ {title}")
            for ch in item.get('changes', []):
                print(f"      {ch['field']}: {ch['old_value']} → {ch['new_value']}")

        elif change_type == ChangeType.DELETED_EVENT.value:
            print(f"  [{i}] - {title}")

        print()


# =============================================================================
# POINT D'ENTREE
# =============================================================================

def main():
    """Point d'entrée principal avec gestion des arguments CLI"""
    parser = argparse.ArgumentParser(
        description="Synchronisation de calendrier iCal multi-sources"
    )
    parser.add_argument(
        '--config',
        default=CONFIG_FILE,
        help=f"Fichier de configuration des sources (défaut: {CONFIG_FILE})"
    )
    parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help="Exécuter sans sauvegarder l'état (pas de modification de etat_{source}.json)"
    )
    parser.add_argument(
        '-n', '--notification',
        action='store_true',
        help="Créer les fichiers de notifications dans le dossier notifications/"
    )

    args = parser.parse_args()

    try:
        sources = Source.load_all_configs(args.config)
    except FileNotFoundError as e:
        logger.error(str(e))
        exit(1)
    except ValueError as e:
        logger.error(f"Erreur de configuration: {e}")
        exit(1)

    if not sources:
        logger.error("Aucune source trouvée dans la configuration")
        exit(1)

    # Construire la config globale pour le fichier process
    date_filter = DateFilter()
    process_data = {
        'timestamp': NOW.isoformat(),
        'status': 'success',
        'config': {
            'config_file': args.config,
            'dry_run': args.dry_run,
            'notification': args.notification,
            'date_debut': date_filter.date_debut.strftime(DATE_FORMAT) if date_filter.date_debut else None,
            'date_fin': date_filter.date_fin.strftime(DATE_FORMAT) if date_filter.date_fin else None,
        },
        'sources': {}
    }

    notification_files = []

    # Traiter chaque source
    for source in sources:
        print(f"\n{'='*60}")
        print(f"SOURCE: {source.name}")
        print(f"{'='*60}")

        try:
            sync = CalendarSync(source=source, dry_run=args.dry_run)
            result = sync.process()

            source_summary = {
                'status': result['status'],
                'events_count': result['events_count'],
                'changes_count': len(result['changes']),
            }
            process_data['sources'][source.name] = source_summary

            # Afficher les changements de cette source
            display_changes(source.name, result.get('changes', []))

            # Sauvegarder la notification si demandé
            if args.notification and result['changes']:
                notification_file = save_notification(
                    source=source.name,
                    changes=result['changes']
                )
                notification_files.append(notification_file)

        except Exception as e:
            logger.error(f"Erreur pour la source '{source.name}': {e}")
            process_data['sources'][source.name] = {
                'status': 'error',
                'error_type': type(e).__name__,
                'error_message': str(e),
            }
            process_data['status'] = 'partial'
            print(f"\n  ERREUR: {e}")

    # Si toutes les sources sont en erreur, status global = error
    statuses = [s['status'] for s in process_data['sources'].values()]
    if all(s == 'error' for s in statuses):
        process_data['status'] = 'error'

    # Sauvegarder le fichier process global
    process_file = save_process(process_data)

    # Résumé final
    print(f"\n{'='*60}")
    print(f"RÉSUMÉ")
    print(f"{'='*60}")
    print(f"\nFichiers générés:")
    for source in sources:
        source_data = process_data['sources'].get(source.name, {})
        if source_data.get('status') == 'success' and not args.dry_run:
            print(f"  - État: {source.state_file}")
    if args.dry_run:
        print(f"  - État: non modifié (dry-run)")
    print(f"  - Processus: {process_file}")
    for nf in notification_files:
        print(f"  - Notification: {nf}")


if __name__ == "__main__":
    main()
