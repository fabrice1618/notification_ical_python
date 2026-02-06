# Google calendar

## 🧩 Principe général

Google Calendar se pilote via la **Google Calendar API** avec :
- OAuth 2.0 (authentification sécurisée)
- La bibliothèque Python officielle `google-api-python-client`

---

## ✅ Étape 1 — Créer un projet Google + activer l’API

1. Va sur **Google Cloud Console**
2. Crée un projet
3. Active **Google Calendar API**
4. Crée des **identifiants OAuth 2.0**
   - Type : *Application de bureau*
5. Télécharge le fichier `credentials.json`

---

## ✅ Étape 2 — Installer les dépendances Python

```bash
pip install --upgrade google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2
```

---

## ✅ Étape 3 — Authentification OAuth (une seule fois)

```python
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pickle
import os

SCOPES = ['https://www.googleapis.com/auth/calendar']

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

service = build('calendar', 'v3', credentials=creds)
```

✅ Une page Google s’ouvrira pour autoriser l’accès.

---

## ✅ Étape 4 — Ajouter un événement

```python
event = {
    'summary': 'Réunion projet',
    'location': 'Paris',
    'description': 'Point hebdomadaire',
    'start': {
        'dateTime': '2026-02-10T10:00:00',
        'timeZone': 'Europe/Paris',
    },
    'end': {
        'dateTime': '2026-02-10T11:00:00',
        'timeZone': 'Europe/Paris',
    },
}

event = service.events().insert(
    calendarId='primary',
    body=event
).execute()

print("Événement créé :", event.get('htmlLink'))
```

---

## ✅ Étape 5 — Mettre à jour un événement existant

```python
event_id = 'ID_DE_L_EVENT'

event = service.events().get(
    calendarId='primary',
    eventId=event_id
).execute()

event['summary'] = 'Réunion projet (mise à jour)'

updated_event = service.events().update(
    calendarId='primary',
    eventId=event_id,
    body=event
).execute()
```

---

## ✅ Étape 6 — Supprimer un événement

```python
service.events().delete(
    calendarId='primary',
    eventId=event_id
).execute()
```

---

## 🧠 Cas courants possibles

✔ Synchroniser un agenda interne  
✔ Mettre à jour automatiquement des rendez-vous  
✔ Créer des événements récurrents  
✔ Gérer plusieurs calendriers  
✔ Script CRON / serveur

---

## ⚠️ Points importants

- Les dates sont en **ISO 8601**
- Le fuseau **Europe/Paris** est important
- Le fichier `token.pickle` doit être conservé
- Pour un serveur → OAuth différent (service account)
