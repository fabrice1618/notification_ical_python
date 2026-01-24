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

# Configuration réseau
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

# Fichiers et dossiers
CONFIG_FILE = "sources.json"
NOTIFICATIONS_DIR = "notifications"
LOG_FILE = "calendar_sync.log"

# Format de date pour la date limite
DATE_FORMAT = "%Y-%m-%d"

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
    NEW_EVENT = "new_event"
    DELETED_EVENT = "deleted_event"
    CONNECTION_ERROR = "connection_error"
    FORMAT_ERROR = "format_error"


class NotificationType(Enum):
    """Types de notifications"""
    INFORMATION = "information"      # Changements mineurs (salle, titre, description)
    NOTIFICATION = "notification"    # Changements importants (dates/heures)
    ERROR = "error"                  # Erreurs de connexion ou format


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
    notification_type: str

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

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Event':
        return cls(**data)


# =============================================================================
# DETECTION DES CHANGEMENTS
# =============================================================================

class ChangeDetector:
    """Détecte et catégorise les changements entre deux événements"""

    @staticmethod
    def detect_changes(old_event: Dict, new_event: Dict) -> List[Change]:
        """Détecte tous les changements entre deux versions d'un événement"""
        changes = []

        # Changement de titre (information)
        if old_event.get(FIELD_TITLE) != new_event.get(FIELD_TITLE):
            changes.append(Change(
                type=ChangeType.TITLE.value,
                field="Titre",
                old_value=old_event.get(FIELD_TITLE),
                new_value=new_event.get(FIELD_TITLE),
                notification_type=NotificationType.INFORMATION.value
            ))

        # Changement de salle (information)
        if old_event.get(FIELD_LOCATION) != new_event.get(FIELD_LOCATION):
            changes.append(Change(
                type=ChangeType.LOCATION.value,
                field="Salle",
                old_value=old_event.get(FIELD_LOCATION),
                new_value=new_event.get(FIELD_LOCATION),
                notification_type=NotificationType.INFORMATION.value
            ))

        # Changement de description (information)
        if old_event.get(FIELD_DESCRIPTION) != new_event.get(FIELD_DESCRIPTION):
            changes.append(Change(
                type=ChangeType.DESCRIPTION.value,
                field="Description",
                old_value=old_event.get(FIELD_DESCRIPTION),
                new_value=new_event.get(FIELD_DESCRIPTION),
                notification_type=NotificationType.INFORMATION.value
            ))

        # Changement d'heure/date de début (notification)
        if old_event.get(FIELD_START) != new_event.get(FIELD_START):
            changes.append(Change(
                type=ChangeType.START_TIME.value,
                field="Date/Heure de début",
                old_value=old_event.get(FIELD_START),
                new_value=new_event.get(FIELD_START),
                notification_type=NotificationType.NOTIFICATION.value
            ))

        # Changement d'heure/date de fin (notification)
        if old_event.get(FIELD_END) != new_event.get(FIELD_END):
            changes.append(Change(
                type=ChangeType.END_TIME.value,
                field="Date/Heure de fin",
                old_value=old_event.get(FIELD_END),
                new_value=new_event.get(FIELD_END),
                notification_type=NotificationType.NOTIFICATION.value
            ))

        return changes


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def load_sources_config(config_file: str) -> Dict:
    """Charge la configuration des sources depuis un fichier JSON"""
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Fichier de configuration introuvable: {config_file}")

    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_notification(source: str, notification_data: Dict):
    """
    Sauvegarde une notification dans un fichier horodaté.

    Args:
        source: Nom de la source
        notification_data: Données de la notification
    """
    # Créer le dossier notifications s'il n'existe pas
    os.makedirs(NOTIFICATIONS_DIR, exist_ok=True)

    # Générer le nom du fichier avec horodatage
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{source}_{timestamp}.json"
    filepath = os.path.join(NOTIFICATIONS_DIR, filename)

    # Sauvegarder la notification
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(notification_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Notification sauvegardée: {filepath}")
    return filepath


# =============================================================================
# CLASSE PRINCIPALE
# =============================================================================

class CalendarSync:
    """Classe principale de synchronisation du calendrier"""

    def __init__(self, source_name: str, calendar_url: str, date_limite: Optional[str] = None, verify_ssl: bool = True):
        """
        Initialise le système de synchronisation

        Args:
            source_name: Nom de la source (utilisé pour les fichiers)
            calendar_url: URL du calendrier iCal (webcal:// ou https://)
            date_limite: Date limite (YYYY-MM-DD) avant laquelle les événements sont ignorés
            verify_ssl: Vérifier le certificat SSL (défaut: True)
        """
        self.source_name = source_name
        self.calendar_url = self._validate_and_normalize_url(calendar_url)
        self.state_file = f"etat_{source_name}.json"
        self.new_file = f"new_{source_name}.json"
        self.change_detector = ChangeDetector()
        self.date_limite = self._parse_date_limite(date_limite)
        self.verify_ssl = verify_ssl

        if not verify_ssl:
            logger.warning(f"Vérification SSL désactivée pour {source_name}")
            # Supprimer les avertissements SSL
            warnings.filterwarnings('ignore', category=InsecureRequestWarning)

    def _parse_date_limite(self, date_limite: Optional[str]) -> Optional[datetime]:
        """Parse la date limite si fournie"""
        if not date_limite:
            return None
        try:
            return datetime.strptime(date_limite, DATE_FORMAT)
        except ValueError:
            logger.warning(f"Format de date limite invalide: {date_limite} (attendu: YYYY-MM-DD)")
            return None

    def _validate_and_normalize_url(self, url: str) -> str:
        """Valide et normalise l'URL du calendrier"""
        # Normaliser webcal:// vers https://
        normalized_url = url.replace("webcal://", "https://")

        # Parser l'URL pour validation
        try:
            parsed = urlparse(normalized_url)
        except Exception:
            raise ValueError(f"URL invalide: {url}")

        # Vérifier le schéma
        if parsed.scheme not in ('http', 'https'):
            raise ValueError(f"Schéma d'URL non supporté: {parsed.scheme}")

        # Vérifier que l'URL a un hôte
        if not parsed.netloc:
            raise ValueError(f"URL sans hôte: {url}")

        return normalized_url

    def fetch_calendar(self) -> Component:
        """Télécharge et parse le calendrier iCal avec retry"""
        last_exception = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Téléchargement du calendrier (tentative {attempt}/{MAX_RETRIES})...")
                response = requests.get(self.calendar_url, timeout=REQUEST_TIMEOUT, verify=self.verify_ssl)
                response.raise_for_status()
                logger.info("Calendrier téléchargé avec succès")
                return Calendar.from_ical(response.text)
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"Échec du téléchargement (tentative {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    import time
                    wait_time = 2 ** attempt  # Backoff exponentiel
                    logger.info(f"Nouvelle tentative dans {wait_time} secondes...")
                    time.sleep(wait_time)
            except Exception as e:
                # Erreur de parsing iCal
                raise ValueError(f"Erreur de format iCal: {e}")

        logger.error(f"Échec du téléchargement après {MAX_RETRIES} tentatives")
        if last_exception is not None:
            raise last_exception
        raise RuntimeError(f"Échec du téléchargement après {MAX_RETRIES} tentatives")

    def parse_events(self, cal: Component) -> Dict[str, Dict]:
        """Parse les événements du calendrier"""
        events = {}

        for component in cal.walk():
            if component.name == "VEVENT":
                uid = component.get('uid')

                # Validation de l'UID
                if not uid:
                    logger.warning("Événement sans UID ignoré")
                    continue

                uid = str(uid).strip()
                if not uid:
                    logger.warning("Événement avec UID vide ignoré")
                    continue

                # Gestion des dates/heures
                start_dt = component.get('dtstart')
                end_dt = component.get('dtend')

                try:
                    start_value = start_dt.dt.isoformat() if start_dt else None
                    end_value = end_dt.dt.isoformat() if end_dt else None
                except Exception as e:
                    logger.warning(f"Erreur de parsing des dates pour {uid}: {e}")
                    start_value = None
                    end_value = None

                event_data = {
                    FIELD_UID: uid,
                    FIELD_TITLE: str(component.get('summary', '') or ''),
                    FIELD_LOCATION: str(component.get('location', '') or ''),
                    FIELD_START: start_value,
                    FIELD_END: end_value,
                    FIELD_DESCRIPTION: str(component.get('description', '') or ''),
                    FIELD_LAST_MODIFIED: datetime.now().isoformat()
                }

                events[uid] = event_data

        logger.info(f"{len(events)} événement(s) parsé(s)")
        return events

    def _is_event_after_date_limite(self, event: Dict) -> bool:
        """Vérifie si l'événement est après la date limite"""
        if not self.date_limite:
            return True  # Pas de limite, tous les événements sont inclus

        start_str = event.get(FIELD_START)
        if not start_str:
            return True  # Pas de date de début, on inclut l'événement

        try:
            # Parser la date ISO (peut être date ou datetime)
            if 'T' in start_str:
                event_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            else:
                event_date = datetime.strptime(start_str, DATE_FORMAT)

            # Comparer uniquement les dates (sans l'heure)
            return event_date.date() >= self.date_limite.date()
        except (ValueError, AttributeError):
            return True  # En cas d'erreur, on inclut l'événement

    def filter_events_by_date(self, events: Dict[str, Dict]) -> Dict[str, Dict]:
        """Filtre les événements selon la date limite"""
        if not self.date_limite:
            return events

        filtered = {
            uid: event for uid, event in events.items()
            if self._is_event_after_date_limite(event)
        }

        excluded_count = len(events) - len(filtered)
        if excluded_count > 0:
            logger.info(f"{excluded_count} événement(s) ignoré(s) (avant {self.date_limite.strftime(DATE_FORMAT)})")

        return filtered

    def load_state(self) -> Dict[str, Dict]:
        """Charge l'état depuis le fichier JSON"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        logger.warning(f"Fichier d'état vide: {self.state_file}")
                        return {}
                    return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Fichier d'état corrompu {self.state_file}: {e}")
                raise ValueError(f"Fichier d'état corrompu: {e}")
            except Exception as e:
                logger.error(f"Erreur lors de la lecture de {self.state_file}: {e}")
                raise
        logger.info(f"Fichier d'état inexistant: {self.state_file}")
        return {}

    def save_state(self, events: Dict[str, Dict]):
        """Sauvegarde l'état dans le fichier JSON de manière atomique"""
        temp_file = f"{self.state_file}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, self.state_file)
            logger.debug(f"État sauvegardé dans {self.state_file}")
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            logger.error(f"Erreur lors de la sauvegarde de {self.state_file}: {e}")
            raise

    def save_new_state(self, events: Dict[str, Dict]):
        """Sauvegarde le nouvel état téléchargé dans new_{source}.json"""
        temp_file = f"{self.new_file}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, self.new_file)
            logger.debug(f"Nouvel état sauvegardé dans {self.new_file}")
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            logger.error(f"Erreur lors de la sauvegarde de {self.new_file}: {e}")
            raise

    def detect_all_changes(self, old_state: Dict, new_state: Dict) -> List[Dict]:
        """
        Détecte tous les changements entre l'ancien et le nouvel état

        Returns:
            Liste des changements détectés
        """
        changes_list = []

        # Traiter les événements modifiés ou existants
        for uid, new_event in new_state.items():
            if uid in old_state:
                old_event = old_state[uid]
                changes = self.change_detector.detect_changes(old_event, new_event)

                for change in changes:
                    changes_list.append({
                        'uid': uid,
                        'event_title': new_event.get(FIELD_TITLE),
                        'type': change.type,
                        'field': change.field,
                        'old_value': change.old_value,
                        'new_value': change.new_value,
                        'notification_type': change.notification_type
                    })
            else:
                # Nouvel événement (nécessite approbation)
                changes_list.append({
                    'uid': uid,
                    'event_title': new_event.get(FIELD_TITLE),
                    'type': ChangeType.NEW_EVENT.value,
                    'field': 'Nouvel événement',
                    'old_value': None,
                    'new_value': new_event.get(FIELD_START),
                    'notification_type': NotificationType.NOTIFICATION.value
                })
                logger.info(f"Nouvel événement détecté: {uid}")

        # Traiter les événements supprimés
        for uid in set(old_state.keys()) - set(new_state.keys()):
            changes_list.append({
                'uid': uid,
                'event_title': old_state[uid].get(FIELD_TITLE),
                'type': ChangeType.DELETED_EVENT.value,
                'field': 'Événement supprimé',
                'old_value': old_state[uid].get(FIELD_TITLE),
                'new_value': None,
                'notification_type': NotificationType.NOTIFICATION.value
            })
            logger.info(f"Événement supprimé détecté: {uid}")

        return changes_list

    def process(self) -> Dict:
        """
        Processus principal de synchronisation

        Returns:
            Dictionnaire avec les résultats de la synchronisation
        """
        logger.info("=" * 60)
        logger.info(f"SYNCHRONISATION - Source: {self.source_name}")
        logger.info("=" * 60)

        result = {
            'source': self.source_name,
            'timestamp': datetime.now().isoformat(),
            'status': 'success',
            'events_count': 0,
            'changes': []
        }

        try:
            # Étape 1 : Charger l'état actuel
            logger.info(f"Chargement de {self.state_file}...")
            old_state = self.load_state()
            logger.info(f"{len(old_state)} événement(s) dans l'état actuel")

            # Étape 2 : Télécharger et parser le calendrier
            cal = self.fetch_calendar()
            logger.info("Analyse des événements...")
            new_state = self.parse_events(cal)
            logger.info(f"{len(new_state)} événement(s) trouvé(s)")

            # Étape 3 : Sauvegarder le nouvel état brut
            logger.info(f"Sauvegarde du nouvel état dans {self.new_file}...")
            self.save_new_state(new_state)

            # Étape 4 : Filtrer selon la date limite
            new_state = self.filter_events_by_date(new_state)
            old_state = self.filter_events_by_date(old_state)
            result['events_count'] = len(new_state)

            # Étape 5 : Détecter les changements
            logger.info("Détection des changements...")
            changes = self.detect_all_changes(old_state, new_state)
            result['changes'] = changes

            if changes:
                logger.info(f"{len(changes)} changement(s) détecté(s)")
            else:
                logger.info("Aucun changement détecté")

            # Étape 6 : Remplacer l'ancien état par le nouveau
            logger.info(f"Mise à jour de {self.state_file}...")
            self.save_state(new_state)

            # Étape 7 : Supprimer le fichier temporaire new_*.json
            if os.path.exists(self.new_file):
                os.remove(self.new_file)
                logger.debug(f"Fichier temporaire supprimé: {self.new_file}")

            # Résumé
            logger.info("=" * 60)
            logger.info("SYNCHRONISATION TERMINÉE")
            logger.info("=" * 60)

        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur de connexion: {e}")
            result['status'] = 'error'
            result['error_type'] = ChangeType.CONNECTION_ERROR.value
            result['error_message'] = str(e)

        except ValueError as e:
            if "format iCal" in str(e) or "corrompu" in str(e):
                logger.error(f"Erreur de format: {e}")
                result['status'] = 'error'
                result['error_type'] = ChangeType.FORMAT_ERROR.value
                result['error_message'] = str(e)
            else:
                raise

        return result


# =============================================================================
# AFFICHAGE
# =============================================================================

def display_changes(changes: List[Dict]):
    """Affiche les changements de manière lisible"""
    if not changes:
        print("\nAucun changement détecté")
        return

    print(f"\n{'='*60}")
    print(f"CHANGEMENTS DETECTES ({len(changes)})")
    print(f"{'='*60}\n")

    for i, change in enumerate(changes, 1):
        notif_type = change.get('notification_type', '').upper()
        print(f"[{i}] [{notif_type}] {change['event_title']}")
        print(f"    Type: {change['type']}")
        print(f"    Champ: {change['field']}")
        if change['old_value']:
            print(f"    Ancien: {change['old_value']}")
        if change['new_value']:
            print(f"    Nouveau: {change['new_value']}")
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
        '-s', '--source',
        required=True,
        help="Nom de la source à synchroniser (défini dans sources.json)"
    )
    parser.add_argument(
        '--config',
        default=CONFIG_FILE,
        help=f"Fichier de configuration des sources (défaut: {CONFIG_FILE})"
    )

    args = parser.parse_args()

    try:
        # Charger la configuration
        logger.info(f"Chargement de la configuration depuis {args.config}...")
        sources = load_sources_config(args.config)

        # Vérifier que la source existe
        if args.source not in sources:
            available = ', '.join(sources.keys())
            logger.error(f"Source '{args.source}' introuvable. Sources disponibles: {available}")
            exit(1)

        source_config = sources[args.source]
        logger.info(f"Source: {args.source} - {source_config.get('description', '')}")

        # Afficher la date limite si configurée
        date_limite = source_config.get('date_limite')
        if date_limite:
            logger.info(f"Date limite: {date_limite} (événements antérieurs ignorés)")

        # Vérification SSL (défaut: True)
        verify_ssl = source_config.get('verify_ssl', True)

        # Créer et exécuter la synchronisation
        sync = CalendarSync(
            source_name=args.source,
            calendar_url=source_config['url'],
            date_limite=date_limite,
            verify_ssl=verify_ssl
        )

        result = sync.process()

        # Sauvegarder la notification
        notification_file = save_notification(
            source=args.source,
            notification_data=result
        )

        # Afficher les changements
        if result['status'] == 'success':
            display_changes(result.get('changes', []))
            print(f"\nFichiers:")
            print(f"  - État: etat_{args.source}.json")
            print(f"  - Notification: {notification_file}")
        else:
            print(f"\nERREUR: {result.get('error_type')}")
            print(f"Message: {result.get('error_message')}")
            print(f"Notification d'erreur: {notification_file}")

    except FileNotFoundError as e:
        logger.error(str(e))
        exit(1)
    except ValueError as e:
        logger.error(f"Erreur de configuration: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        exit(1)


if __name__ == "__main__":
    main()
