# Doctolib Arztsuche - Separate Anwendung

Eine eigenständige Flask-Anwendung für die Suche nach Ärzten auf Doctolib basierend auf Ort und Fachrichtung.

## Features

- 🔍 **Ortsbasierte Suche**: Suche nach Ärzten in einer bestimmten Stadt oder PLZ
- 🏥 **Fachrichtungsfilter**: Auswahl aus 15+ medizinischen Fachrichtungen
- 💳 **Versicherungstyp**: Gesetzlich oder privat versichert
- 📋 **Arztprofile**: Direkte Links zu Doctolib-Profilen
- 📅 **Buchungs-URLs**: Automatische Erkennung von Terminbuchungs-Links
- 📱 **Responsive Design**: Funktioniert auf Desktop und Mobile

## Installation

1. Abhängigkeiten sind bereits in der Haupt-`requirements.txt` enthalten
2. Starten Sie die Suchanwendung:

```bash
python search_app.py
```

3. Öffnen Sie Ihren Browser und gehen Sie zu:
```
http://localhost:5001
```

## Verwendung

1. **Ort eingeben**: Stadt oder Postleitzahl (z.B. "Ulm" oder "89073")
2. **Fachrichtung wählen**: Aus der Dropdown-Liste auswählen
3. **Versicherungstyp**: Gesetzlich oder privat
4. **Suchen**: Klicken Sie auf "Suchen"
5. **Ergebnisse**: Durchsuchen Sie die gefundenen Ärzte
6. **Termine prüfen**: Klicken Sie auf "Termine prüfen" um Buchungs-URLs zu finden

## Verfügbare Fachrichtungen

- Allgemeinmedizin
- Hautarzt / Dermatologie  
- Zahnarzt
- Gynäkologie / Frauenheilkunde
- Orthopädie
- Augenheilkunde
- HNO (Hals-Nasen-Ohren)
- Innere Medizin
- Neurologie
- Psychiatrie
- Kardiologie
- Radiologie
- Urologie
- Chirurgie
- Anästhesie

## Integration mit der Hauptanwendung

Die gefundenen Buchungs-URLs können direkt in der Hauptanwendung (`app.py` auf Port 5000) verwendet werden, um nach verfügbaren Terminen zu suchen.

## API-Endpunkte

### POST `/search`
Sucht nach Ärzten basierend auf den angegebenen Kriterien.

**Request Body:**
```json
{
    "location": "Ulm",
    "speciality": "hautarzt", 
    "insurance_sector": "public"
}
```

**Response:**
```json
{
    "success": true,
    "doctors": [...],
    "total_found": 5,
    "location": "Ulm",
    "speciality": "hautarzt"
}
```

### POST `/get_booking_url`
Versucht die Buchungs-URL von einer Arzt-Seite zu extrahieren.

**Request Body:**
```json
{
    "doctor_url": "https://www.doctolib.de/hautarzt/ulm/dr-mustermann"
}
```

**Response:**
```json
{
    "success": true,
    "booking_url": "https://www.doctolib.de/booking/..."
}
```

## Technische Details

- **Port**: 5001 (um Konflikte mit der Hauptanwendung zu vermeiden)
- **Templates**: Eigener `search_templates` Ordner
- **HTML-Parsing**: Einfache Regex-basierte Extraktion von Doktor-Informationen
- **Fehlerbehandlung**: Umfassende Fehlerbehandlung für alle API-Calls

## Datenschutz

Diese Anwendung führt nur öffentliche Suchanfragen durch und speichert keine persönlichen Daten. Alle Anfragen werden direkt an Doctolib weitergeleitet.
