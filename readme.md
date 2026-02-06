# Système de Synchronisation de Calendrier iCal

## Description

Système de surveillance de calendriers iCal distants avec support multi-sources. Le système télécharge périodiquement les calendriers, détecte les modifications et génère un fichier de résultat horodaté.

## Fonctionnalités

- **Multi-sources** : Traitement de toutes les sources en une seule exécution
- **Détection des changements** : Comparaison avec l'état précédent
- **Fichier résultat unique** : Un fichier `{timestamp}_calendar_sync.json` par exécution
- **Filtrage par dates** : Plage de dates configurable (constantes globales)
- **Conversion fuseau horaire** : Dates affichées en heure locale (Europe/Paris)
- **Gestion des erreurs** : Les erreurs d'une source n'empêchent pas le traitement des autres

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
    "description": "Calendrier des cours"
  },
  "ecole": {
    "url": "https://serveur-ecole.fr/calendar.ics",
    "description": "Calendrier école",
    "verify_ssl": false
  }
}
```

### Paramètres de source

| Paramètre | Obligatoire | Description |
|-----------|-------------|-------------|
| `url` | Oui | URL du calendrier iCal (webcal:// ou https://) |
| `description` | Non | Description de la source |
| `verify_ssl` | Non | Vérifier le certificat SSL (défaut: true) |

### Constantes globales (dans calendar_sync.py)

```python
DATE_DEBUT = "2025-08-01"    # Ignorer événements avant cette date
DATE_FIN = "2026-07-31"      # Ignorer événements après cette date
TIMEZONE = ZoneInfo("Europe/Paris")
DISPLAY_DATE_FORMAT = "%d/%m/%Y %H:%M"
```

## Utilisation

```bash
# Synchroniser toutes les sources
python calendar_sync.py

# Mode dry-run (pas de modification des fichiers d'état)
python calendar_sync.py -d

# Avec un fichier de configuration personnalisé
python calendar_sync.py --config mes_sources.json

# Afficher le dernier résultat
python print_calendar_sync.py

# Afficher un résultat spécifique
python print_calendar_sync.py -f data_sync/20260206_080000_calendar_sync.json
```

### Automatisation (Cron)

```bash
# Synchroniser toutes les heures
0 * * * * /usr/bin/python3 /path/to/calendar_sync.py >> /var/log/calendar_sync.log 2>&1
```

## Structure des Fichiers

```
projet/
├── calendar_sync.py          # Script principal
├── print_calendar_sync.py    # Affichage des résultats
├── sources.json              # Configuration des sources (gitignored)
├── sources_example.json      # Exemple de configuration
├── data/
│   ├── etat_cours.json       # État pour source "cours"
│   ├── etat_ecole.json       # État pour source "ecole"
│   └── calendar_sync.log     # Fichier de log
└── data_sync/
    └── 20260206_080000_calendar_sync.json
```

## Format du Fichier Résultat

Le fichier `{timestamp}_calendar_sync.json` contient :

```json
{
  "timestamp": "20260206_080000",
  "status": "success",
  "config": {
    "config_file": "sources.json",
    "dry_run": false,
    "date_debut": "2025-08-01",
    "date_fin": "2026-07-31"
  },
  "sources": {
    "cours": {
      "status": "success",
      "events_count": 200,
      "changes_count": 3,
      "changes": [...]
    },
    "ecole": {
      "status": "success",
      "events_count": 54,
      "changes_count": 0,
      "changes": []
    }
  }
}
```

### Types de changements

```json
// Nouvel événement
{
  "type": "new_event",
  "event": {
    "uid": "event-123",
    "title": "Cours de maths",
    "location": "Salle A101",
    "start": "15/03/2026 14:00",
    "end": "15/03/2026 16:00",
    "description": "",
    "status": ""
  }
}

// Événement modifié
{
  "type": "modified_event",
  "event": { ... },
  "previous": { ... },
  "changes": [
    {
      "type": "location_change",
      "field": "Salle",
      "old_value": "A101",
      "new_value": "B203"
    },
    {
      "type": "start_time_change",
      "field": "Date/Heure de début",
      "old_value": "15/03/2026 14:00",
      "new_value": "15/03/2026 15:00"
    }
  ]
}

// Événement supprimé
{
  "type": "deleted_event",
  "event": { ... }
}
```

### Types de modifications

| Type | Description |
|------|-------------|
| `new_event` | Nouvel événement |
| `modified_event` | Événement modifié |
| `deleted_event` | Événement supprimé |
| `title_change` | Changement de titre |
| `location_change` | Changement de salle |
| `description_change` | Changement de description |
| `status_change` | Changement de statut |
| `start_time_change` | Changement date/heure début |
| `end_time_change` | Changement date/heure fin |

### Valeurs de status

| Status | Description |
|--------|-------------|
| `success` | Toutes les sources traitées avec succès |
| `partial` | Certaines sources en erreur |
| `error` | Toutes les sources en erreur |

## Affichage avec print_calendar_sync.py

```
Fichier: 20260206_080000_calendar_sync.json
Période: 2025-08-01 → 2026-07-31

[cours] 200 événements, 3 changements

  NOUVEAUX (1)
    + 15/03/2026 14:00 | Cours de maths @ Salle A101

  MODIFIÉS (1)
    ~ 20/03/2026 09:00 | TD Physique
        Salle: A101 → B203

  SUPPRIMÉS (1)
    - 10/03/2026 10:00 | Cours annulé

[ecole] 54 événements, 0 changements
```

## Configuration Google Calendar

1. Ouvrir [Google Calendar](https://calendar.google.com)
2. Paramètres > Paramètres
3. Sélectionner le calendrier
4. Copier l'**Adresse secrète au format iCal**
5. Ajouter l'URL dans `sources.json`
