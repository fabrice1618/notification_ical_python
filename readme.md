# Systeme de Synchronisation de Calendrier iCal

## Description

Systeme de surveillance de calendriers iCal distants avec support multi-sources. Le systeme telecharge periodiquement les calendriers, detecte les modifications et genere des notifications horodatees.

## Fonctionnalites

- **Multi-sources** : Configuration de plusieurs calendriers dans un fichier JSON
- **Detection des changements** : Comparaison avec l'etat precedent
- **Notifications horodatees** : Un fichier par execution dans `notifications/`
- **Date limite** : Possibilite d'ignorer les evenements passes
- **Gestion des erreurs** : Notifications en cas d'erreur de connexion ou de format

## Types de Notifications

| Type | Description | Exemples |
|------|-------------|----------|
| `information` | Changements mineurs | Salle, titre, description |
| `notification` | Changements importants | Dates/heures, ajout, suppression |
| `error` | Erreurs | Connexion, format iCal |

## Installation

```bash
pip install icalendar requests
```

## Configuration

### Fichier sources.json

```json
{
  "cours": {
    "url": "webcal://example.com/calendar.ics",
    "description": "Calendrier des cours",
    "date_limite": "2026-01-01"
  },
  "perso": {
    "url": "https://calendar.google.com/calendar/ical/.../basic.ics",
    "description": "Calendrier personnel"
  }
}
```

### Parametres de source

| Parametre | Obligatoire | Description |
|-----------|-------------|-------------|
| `url` | Oui | URL du calendrier iCal (webcal:// ou https://) |
| `description` | Non | Description de la source |
| `date_limite` | Non | Date (YYYY-MM-DD) avant laquelle les evenements sont ignores |
| `verify_ssl` | Non | Verifier le certificat SSL (defaut: true). Mettre `false` pour les serveurs avec certificats auto-signes |

### Constantes (dans le code)

```python
REQUEST_TIMEOUT = 30        # Timeout HTTP en secondes
MAX_RETRIES = 3             # Nombre de tentatives
CONFIG_FILE = "sources.json"
NOTIFICATIONS_DIR = "notifications"
```

## Utilisation

```bash
# Synchroniser une source
python calendar_sync.py -s cours

# Avec un fichier de configuration personnalise
python calendar_sync.py -s cours --config mes_sources.json
```

### Automatisation (Cron)

```bash
# Synchroniser toutes les heures
0 * * * * /usr/bin/python3 /path/to/calendar_sync.py -s cours >> /var/log/calendar_sync.log 2>&1
```

## Structure des Fichiers

```
projet/
├── calendar_sync.py          # Script principal
├── sources.json              # Configuration des sources
├── calendar_sync.log         # Fichier de log
├── etat_cours.json           # Etat valide pour source "cours"
├── etat_perso.json           # Etat valide pour source "perso"
└── notifications/
    ├── cours_20260124_143022.json
    └── perso_20260124_143500.json
```

## Format des Notifications

### Succes

```json
{
  "source": "cours",
  "timestamp": "2026-01-24T14:30:22",
  "status": "success",
  "events_count": 15,
  "changes": [
    {
      "uid": "event-123",
      "event_title": "Cours de maths",
      "type": "location_change",
      "field": "Salle",
      "old_value": "A101",
      "new_value": "B202",
      "notification_type": "information"
    },
    {
      "uid": "event-456",
      "event_title": "TD Physique",
      "type": "new_event",
      "field": "Nouvel evenement",
      "old_value": null,
      "new_value": "2026-01-25T09:00:00",
      "notification_type": "notification"
    }
  ]
}
```

### Erreur

```json
{
  "source": "cours",
  "timestamp": "2026-01-24T14:30:22",
  "status": "error",
  "error_type": "connection_error",
  "error_message": "Connection timed out",
  "events_count": 0,
  "changes": []
}
```

## Types de Changements

| Type | Description | notification_type |
|------|-------------|-------------------|
| `title_change` | Changement de titre | information |
| `location_change` | Changement de salle | information |
| `description_change` | Changement de description | information |
| `start_time_change` | Changement date/heure debut | notification |
| `end_time_change` | Changement date/heure fin | notification |
| `new_event` | Nouvel evenement | notification |
| `deleted_event` | Evenement supprime | notification |
| `connection_error` | Erreur de connexion | error |
| `format_error` | Erreur de format iCal | error |

## Architecture

### Classes

- **CalendarSync** : Orchestrateur principal
- **ChangeDetector** : Detection et categorisation des changements
- **Event** : Representation d'un evenement
- **Change** : Representation d'un changement

### Flux de traitement

```
1. Chargement configuration (sources.json)
2. Chargement etat actuel (etat_{source}.json)
3. Telechargement du calendrier iCal
4. Parsing des evenements
5. Filtrage selon date_limite (si configuree)
6. Detection des changements
7. Mise a jour de l'etat (etat_{source}.json)
8. Generation notification horodatee
```

## Configuration Google Calendar

1. Ouvrir [Google Calendar](https://calendar.google.com)
2. Parametres > Parametres
3. Selectionner le calendrier
4. Copier l'**Adresse secrete au format iCal**
5. Ajouter l'URL dans `sources.json`
