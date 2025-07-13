from flask import Flask, render_template, request, jsonify
import json
import urllib.parse
import urllib.request
import re
import traceback
import random
from datetime import datetime

# Optionale Geocoding-Bibliotheken
try:
    from geopy.geocoders import Nominatim
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False
    print("DEBUG: geopy nicht verfügbar. Verwende zufällige Koordinaten.")

try:
    import pgeocode
    PGEOCODE_AVAILABLE = True
except ImportError:
    PGEOCODE_AVAILABLE = False
    print("DEBUG: pgeocode nicht verfügbar.")

app = Flask(__name__, template_folder='search_templates')

def get_specialities():
    """
    Gibt eine Liste der verfügbaren Fachrichtungen zurück
    """
    return {
        'allgemeinmedizin': 'Allgemeinmedizin',
        'hautarzt': 'Hautarzt / Dermatologie',
        'zahnarzt': 'Zahnarzt',
        'gynakologe': 'Gynäkologie / Frauenheilkunde',
        'orthopade': 'Orthopädie',
        'augenarzt': 'Augenheilkunde',
        'hno': 'HNO (Hals-Nasen-Ohren)',
        'internist': 'Innere Medizin',
        'neurologe': 'Neurologie',
        'psychiater': 'Psychiatrie',
        'kardiologe': 'Kardiologie',
        'radiologe': 'Radiologie',
        'urologe': 'Urologie',
        'chirurg': 'Chirurgie',
        'anaesthesist': 'Anästhesie'
    }

def search_doctors_by_location(location, speciality, insurance_sector="public"):
    """
    Sucht Ärzte basierend auf Ort, Fachrichtung und Versicherungstyp
    Verwendet die echte Doctolib phs_proxy API mit korrektem Payload-Format
    """
    try:
        # Verwende die echte Doctolib phs_proxy API
        api_url = 'https://www.doctolib.de/phs_proxy/raw?page=0'
        
        # Erstelle Location-Objekt basierend auf dem funktionierenden Payload
        location_data = create_location_object(location)
        
        # POST-Daten im korrekten Format (basierend auf funktionierendem Payload)
        post_data = {
            "keyword": speciality,
            "location": location_data,
            "filters": {
                "insuranceSector": insurance_sector
            }
        }
        
        # Konvertiere zu JSON
        json_data = json.dumps(post_data).encode('utf-8')
        
        print(f"DEBUG: API-URL: {api_url}")
        print(f"DEBUG: POST-Daten: {json.dumps(post_data, indent=2, ensure_ascii=False)}")
        
        # Erstelle POST-Request mit vollständigen Headers
        request_obj = urllib.request.Request(api_url, data=json_data, method='POST')
        request_obj.add_header(
            'User-Agent',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        )
        request_obj.add_header('Accept', 'application/json, text/plain, */*')
        request_obj.add_header('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
        request_obj.add_header('Content-Type', 'application/json')
        request_obj.add_header('Referer', 'https://www.doctolib.de/')
        request_obj.add_header('X-Requested-With', 'XMLHttpRequest')
        request_obj.add_header('Origin', 'https://www.doctolib.de')
        
        # Führe API-Call aus
        with urllib.request.urlopen(request_obj) as response:
            status_code = response.getcode()
            print(f"DEBUG: API Status Code: {status_code}")
            
            if status_code == 200:
                # Lese JSON-Response
                response_data = response.read().decode('utf-8')
                print(f"DEBUG: Response-Länge: {len(response_data)} Zeichen")
                
                # Parse JSON
                api_data = json.loads(response_data)
                print(f"DEBUG: JSON-Keys: {list(api_data.keys()) if isinstance(api_data, dict) else 'Not a dict'}")
                
                # Extrahiere Ärzte aus der API-Response
                doctors = extract_doctors_from_api(api_data, speciality, location)
                
                return {
                    'success': True,
                    'search_url': api_url,
                    'location': location,
                    'speciality': speciality,
                    'insurance_sector': insurance_sector,
                    'doctors': doctors,
                    'total_found': len(doctors),
                    'api_response_keys': list(api_data.keys()) if isinstance(api_data, dict) else None
                }
            else:
                return {
                    'success': False,
                    'error': f'API returned status code {status_code}',
                    'doctors': [],
                    'total_found': 0
                }
        
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        return {
            'success': False,
            'error': f'HTTP Error: {e.code} - {e.reason}',
            'doctors': [],
            'total_found': 0
        }
    except Exception as e:
        print(f"Fehler bei der API-Suche: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f'Fehler bei der API-Suche: {str(e)}',
            'doctors': [],
            'total_found': 0
        }

def extract_doctors_from_api(api_data, speciality, location):
    """
    Extrahiert Doktor-Informationen aus der Doctolib phs_proxy API-Response
    """
    doctors = []
    
    try:
        print(f"DEBUG: API-Daten-Typ: {type(api_data)}")
        
        # Speichere API-Response für Debugging
        with open('debug_api_response.json', 'w', encoding='utf-8') as f:
            json.dump(api_data, f, indent=2, ensure_ascii=False)
        print("DEBUG: API-Response in debug_api_response.json gespeichert")
        
        # Debug: Zeige die ersten paar Provider-Objekte zur Analyse
        if isinstance(api_data, dict) and 'healthcareProviders' in api_data:
            providers = api_data['healthcareProviders']
            if isinstance(providers, list) and len(providers) > 0:
                print(f"DEBUG: Erste Provider-Struktur: {json.dumps(providers[0], indent=2, ensure_ascii=False)[:500]}...")
                # Suche nach agenda-relevanten Feldern
                first_provider = providers[0]
                agenda_fields = [key for key in first_provider.keys() if 'agenda' in key.lower()]
                print(f"DEBUG: Agenda-relevante Felder im ersten Provider: {agenda_fields}")
        
        # Die phs_proxy API hat 'healthcareProviders' als Hauptkey
        if isinstance(api_data, dict) and 'healthcareProviders' in api_data:
            healthcare_providers = api_data['healthcareProviders']
            total_count = api_data.get('total', 0)
            
            print(f"DEBUG: Gefunden {total_count} Gesundheitsdienstleister")
            print(f"DEBUG: healthcareProviders ist {type(healthcare_providers)} mit {len(healthcare_providers) if isinstance(healthcare_providers, list) else 'unbekannt'} Einträgen")
            
            if isinstance(healthcare_providers, list):
                for i, provider in enumerate(healthcare_providers[:15]):  # Begrenze auf 15
                    print(f"DEBUG: Verarbeite Anbieter {i+1}: {type(provider)}")
                    
                    if isinstance(provider, dict):
                        doctor = extract_doctor_from_provider(provider, speciality, location)
                        if doctor:
                            doctors.append(doctor)
                            print(f"DEBUG: Arzt hinzugefügt: {doctor.get('name', 'Unbekannt')}")
        else:
            print("DEBUG: Keine 'healthcareProviders' in der API-Response gefunden")
            print(f"DEBUG: Verfügbare Keys: {list(api_data.keys()) if isinstance(api_data, dict) else 'Keine Dict'}")
    
    except Exception as e:
        print(f"DEBUG: Fehler beim Extrahieren der API-Daten: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"DEBUG: Insgesamt {len(doctors)} Ärzte aus API extrahiert")
    return doctors

def extract_doctor_from_provider(provider_data, speciality, location):
    """
    Extrahiert einen einzelnen Arzt aus einem healthcareProvider-Objekt
    """
    try:
        # Die API gibt bereits die korrekte Struktur zurück
        doctor_name = None
        
        # Name aus firstName + name (title) konstruieren
        first_name = provider_data.get('firstName', '')
        last_name = provider_data.get('name', '')
        title = provider_data.get('title', '')
        
        if first_name and last_name:
            doctor_name = f"{title} {first_name} {last_name}".strip()
        elif last_name:
            doctor_name = f"{title} {last_name}".strip()
        
        # URL aus link-Feld
        doctor_url = provider_data.get('link', '')
        if doctor_url and not doctor_url.startswith('http'):
            doctor_url = 'https://www.doctolib.de' + doctor_url
        
        # Slug aus URL extrahieren
        slug = ''
        if doctor_url and '/' in doctor_url:
            slug = doctor_url.split('/')[-1]
        
        # Adresse aus location-Objekt
        address = ''
        location_data = provider_data.get('location', {})
        if isinstance(location_data, dict):
            street = location_data.get('address', '')
            city = location_data.get('city', location)
            postal_code = location_data.get('zipcode', '')
            
            if street and city:
                address = f"{street}, {postal_code} {city}".strip()
            elif city:
                address = f"{postal_code} {city}".strip()
        
        # Fachrichtung aus speciality-Objekt
        speciality_name = ''
        speciality_data = provider_data.get('speciality', {})
        if isinstance(speciality_data, dict):
            speciality_name = speciality_data.get('name', speciality)
        else:
            speciality_name = speciality
        
        # Geschlecht
        gender = provider_data.get('gender', '')
        
        # Online-Buchung verfügbar
        online_booking = provider_data.get('onlineBooking', False)
        
        # Agenda IDs extrahieren für Terminbuchung
        agenda_ids = []
        
        # Hauptquelle: onlineBooking.agendaIds
        online_booking_data = provider_data.get('onlineBooking', {})
        if isinstance(online_booking_data, dict) and 'agendaIds' in online_booking_data:
            agenda_ids = online_booking_data['agendaIds']
        
        # Fallback-Quellen
        elif 'agendaIds' in provider_data:
            agenda_ids = provider_data['agendaIds']
        elif 'agenda_ids' in provider_data:
            agenda_ids = provider_data['agenda_ids']
        elif 'agendas' in provider_data:
            # Falls die IDs in einem agendas-Array stehen
            agendas = provider_data['agendas']
            if isinstance(agendas, list):
                agenda_ids = [agenda.get('id') for agenda in agendas if isinstance(agenda, dict) and 'id' in agenda]
        
        # Visit Motive ID extrahieren
        visit_motive_id = None
        matched_visit_motive = provider_data.get('matchedVisitMotive', {})
        if isinstance(matched_visit_motive, dict) and 'visitMotiveId' in matched_visit_motive:
            visit_motive_id = matched_visit_motive['visitMotiveId']
        
        print(f"DEBUG: Gefundene agenda_ids für {doctor_name}: {agenda_ids}")
        print(f"DEBUG: Gefundene visit_motive_id für {doctor_name}: {visit_motive_id}")
        
        # Validiere dass wir mindestens einen Namen haben
        if doctor_name and len(doctor_name.strip()) > 2:
            return {
                'name': doctor_name.strip(),
                'url': doctor_url or f"https://www.doctolib.de/{speciality}/{location.lower()}/{slug}",
                'speciality': speciality_name,
                'slug': slug,
                'practice_name': '',  # Nicht direkt verfügbar in dieser API-Struktur
                'address': address or location,
                'phone': '',  # Nicht in der öffentlichen API verfügbar
                'gender': gender,
                'online_booking': online_booking,
                'id': provider_data.get('id', ''),
                'agenda_ids': agenda_ids,
                'visit_motive_id': visit_motive_id
            }
        
        print(f"DEBUG: Arzt abgelehnt - Name zu kurz oder nicht gefunden: '{doctor_name}'")
        return None
        
    except Exception as e:
        print(f"DEBUG: Fehler beim Extrahieren einzelner Arzt-Daten: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_single_doctor(doctor_data, speciality, location):
    """
    Extrahiert einen einzelnen Arzt aus der API-Response
    """
    try:
        # Mögliche Keys für verschiedene Arzt-Informationen
        name_keys = ['name', 'full_name', 'display_name', 'title', 'doctor_name']
        url_keys = ['url', 'profile_url', 'link', 'href', 'booking_url']
        practice_keys = ['practice_name', 'clinic_name', 'office_name', 'institution']
        address_keys = ['address', 'location', 'street_address', 'full_address']
        phone_keys = ['phone', 'telephone', 'phone_number', 'contact_phone']
        
        # Extrahiere Name
        doctor_name = None
        for key in name_keys:
            if key in doctor_data and doctor_data[key]:
                doctor_name = str(doctor_data[key]).strip()
                break
        
        if not doctor_name:
            # Fallback: Versuche aus anderen Feldern zu konstruieren
            first_name = doctor_data.get('first_name', '')
            last_name = doctor_data.get('last_name', '')
            if first_name and last_name:
                doctor_name = f"Dr. {first_name} {last_name}"
        
        # Extrahiere URL
        doctor_url = None
        for key in url_keys:
            if key in doctor_data and doctor_data[key]:
                url = str(doctor_data[key])
                if url.startswith('/'):
                    doctor_url = 'https://www.doctolib.de' + url
                elif url.startswith('http'):
                    doctor_url = url
                break
        
        # Extrahiere weitere Informationen
        practice_name = ''
        for key in practice_keys:
            if key in doctor_data and doctor_data[key]:
                practice_name = str(doctor_data[key]).strip()
                break
        
        address = ''
        for key in address_keys:
            if key in doctor_data and doctor_data[key]:
                address = str(doctor_data[key]).strip()
                break
        
        phone = ''
        for key in phone_keys:
            if key in doctor_data and doctor_data[key]:
                phone = str(doctor_data[key]).strip()
                break
        
        # Erstelle Slug aus Namen oder URL
        slug = ''
        if doctor_url:
            slug = doctor_url.split('/')[-1]
        elif doctor_name:
            slug = doctor_name.lower().replace(' ', '-').replace('dr.', 'dr')
        
        # Validiere dass wir mindestens einen Namen haben
        if doctor_name and len(doctor_name) > 2:
            return {
                'name': doctor_name,
                'url': doctor_url or f"https://www.doctolib.de/{speciality}/{location.lower()}/{slug}",
                'speciality': speciality,
                'slug': slug,
                'practice_name': practice_name,
                'address': address or location,
                'phone': phone
            }
        
        return None
        
    except Exception as e:
        print(f"DEBUG: Fehler beim Extrahieren einzelner Arzt-Daten: {e}")
        return None

def extract_doctors_from_search_page(html_content, speciality):
    """
    Extrahiert Doktor-Informationen aus der Doctolib-Suchergebnisseite
    Realistischere Patterns basierend auf echter Doctolib-Struktur
    """
    doctors = []
    
    try:
        print(f"DEBUG: HTML-Länge: {len(html_content)} Zeichen")
        
        # Speichere HTML-Sample für Debugging
        with open('debug_html_sample.txt', 'w', encoding='utf-8') as f:
            f.write(html_content[:10000])  # Erste 10000 Zeichen
        print("DEBUG: HTML-Sample in debug_html_sample.txt gespeichert")
        
        # Realistische Patterns für Doctolib-Arzt-Profile
        # Basierend auf der echten Doctolib-Struktur
        link_patterns = [
            # Typische Doctolib-Arzt-URLs
            rf'href="(/{speciality}/[^/]+/[^"]*dr-[^"]*)"',
            rf'href="(/{speciality}/[^/]+/[^"]*)"',
            # Alle Arzt-Links mit der Fachrichtung
            rf'href="([^"]*{speciality}[^"]*dr-[^"]*)"',
            # Profile-Links
            r'href="([^"]*profile[^"]*)"',
            # Direkte Links mit Ärztenamen
            r'href="([^"]*dr-[a-z-]+[^"]*)"',
            # Links die wie Ärzte aussehen
            r'href="([^"]*[a-z]+-[a-z]+-[a-z]+[^"]*)"'
        ]
        
        found_links = set()
        
        for pattern in link_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            print(f"DEBUG: Pattern '{pattern}' fand {len(matches)} Links")
            
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                
                # Filter irrelevante Links
                skip_patterns = [
                    'javascript:', 'mailto:', '#', '.css', '.js', '.png', '.jpg', 
                    'cookie', 'legal', 'impressum', 'datenschutz', 'agb',
                    'login', 'session', 'icon', 'favicon', 'manifest'
                ]
                
                if any(skip in match.lower() for skip in skip_patterns):
                    continue
                
                # Muss mindestens einen Namen-ähnlichen Teil haben
                if not re.search(r'[a-z]+-[a-z]+', match.lower()):
                    continue
                
                # Normalisiere die URL
                if match.startswith('/'):
                    full_url = 'https://www.doctolib.de' + match
                elif match.startswith('http'):
                    full_url = match
                else:
                    continue
                
                if full_url not in found_links and len(full_url) > 30:  # Mindestlänge
                    found_links.add(full_url)
                    print(f"DEBUG: Gefundener Link: {full_url}")
        
        print(f"DEBUG: Insgesamt {len(found_links)} eindeutige Links gefunden")
        
        # Wenn keine Links gefunden wurden, versuche eine andere Strategie
        if len(found_links) == 0:
            print("DEBUG: Keine Links gefunden, versuche breitere Suche...")
            
            # Suche nach allen href-Attributen
            all_links = re.findall(r'href="([^"]+)"', html_content)
            print(f"DEBUG: Insgesamt {len(all_links)} Links in der Seite gefunden")
            
            # Filtere die relevanten
            for link in all_links:
                if (speciality in link.lower() or 
                    'doctor' in link.lower() or 
                    'arzt' in link.lower() or
                    re.search(r'/[a-z]+-[a-z]+-[a-z]+', link)):
                    
                    if not any(skip in link.lower() for skip in ['css', 'js', 'png', 'jpg', 'icon']):
                        full_url = link if link.startswith('http') else 'https://www.doctolib.de' + link
                        found_links.add(full_url)
                        print(f"DEBUG: Zusätzlicher Link: {full_url}")
                        
                        if len(found_links) >= 10:  # Begrenze auf 10
                            break
        
        # Verarbeite die ersten 10 Links
        for i, link in enumerate(list(found_links)[:10]):
            print(f"DEBUG: Verarbeite Link {i+1}: {link}")
            
            # Extrahiere Informationen aus der URL
            url_parts = link.split('/')
            if len(url_parts) >= 4:
                doctor_slug = url_parts[-1]
                
                # Bereinige den Slug
                if '?' in doctor_slug:
                    doctor_slug = doctor_slug.split('?')[0]
                
                # Erstelle einen Namen aus dem Slug
                doctor_name = create_name_from_slug(doctor_slug)
                
                if doctor_name and len(doctor_name) > 3:
                    doctors.append({
                        'name': doctor_name,
                        'url': link,
                        'speciality': speciality,
                        'slug': doctor_slug,
                        'practice_name': '',
                        'address': extract_city_from_url(link),
                        'phone': ''
                    })
                    print(f"DEBUG: Arzt hinzugefügt: {doctor_name}")
    
    except Exception as e:
        print(f"DEBUG: Fehler beim Parsen: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"DEBUG: Insgesamt {len(doctors)} Ärzte extrahiert")
    return doctors

def create_name_from_slug(slug):
    """Erstelle einen Arzt-Namen aus einem URL-Slug"""
    try:
        # Entferne häufige Präfixe
        name_part = slug
        for prefix in ['dr-', 'prof-', 'prof-dr-', 'med-']:
            if name_part.startswith(prefix):
                name_part = name_part[len(prefix):]
        
        # Teile in Wörter und kapitalisiere
        words = name_part.split('-')
        name_words = []
        
        for word in words:
            if len(word) > 1 and word.isalpha():
                name_words.append(word.capitalize())
        
        if len(name_words) >= 2:
            return 'Dr. ' + ' '.join(name_words)
        elif len(name_words) == 1:
            return 'Dr. ' + name_words[0]
        
        return None
        
    except:
        return None

def extract_city_from_url(url):
    """Extrahiere die Stadt aus einer Doctolib-URL"""
    try:
        parts = url.split('/')
        if len(parts) >= 5:
            city = parts[4]  # Meist an Position 4: /hautarzt/ulm/dr-name
            return city.capitalize()
        return ''
    except:
        return ''

def extract_doctor_name_from_html(html_content, doctor_link):
    """
    Versucht den echten Doktor-Namen aus dem HTML zu extrahieren
    """
    try:
        # Suche nach dem Namen in der Nähe des Links
        link_escaped = re.escape(doctor_link)
        
        # Pattern für Namen in verschiedenen HTML-Strukturen
        patterns = [
            rf'{link_escaped}[^>]*>([^<]+)<',
            rf'{link_escaped}[^>]*>[^<]*<[^>]*>([^<]+)',
            rf'href="{link_escaped}"[^>]*>.*?([A-Z][a-z]+ [A-Z][a-z]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            if match:
                name = match.group(1).strip()
                # Bereinige den Namen
                name = re.sub(r'<[^>]+>', '', name)  # Entferne HTML-Tags
                name = re.sub(r'\s+', ' ', name)     # Normalisiere Whitespace
                if len(name) > 3 and not name.lower().startswith('termin'):
                    return name
        
        return None
        
    except Exception as e:
        print(f"Fehler beim Extrahieren des Namens: {e}")
        return None

def get_booking_url_from_doctor_page(doctor_url):
    """
    Versucht die Buchungs-URL von der Doktor-Seite zu extrahieren
    Verwendet eine bessere Methode mit der Doctolib-API
    """
    try:
        # Extrahiere den Doktor-Slug aus der URL
        url_parts = doctor_url.split('/')
        if len(url_parts) >= 5:
            doctor_slug = url_parts[-1]
            
            # Verwende die Doctolib Info-API
            info_url = f'https://www.doctolib.de/online_booking/api/slot_selection_funnel/v1/info.json?profile_slug={doctor_slug}'
            
            request_obj = urllib.request.Request(info_url)
            request_obj.add_header(
                'User-Agent',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            request_obj.add_header('Accept', 'application/json')
            
            response = urllib.request.urlopen(request_obj).read().decode('utf-8')
            data = json.loads(response)
            
            if 'data' in data and 'profile' in data['data']:
                profile = data['data']['profile']
                
                # Erstelle die Buchungs-URL
                if 'booking_url_base' in profile:
                    return profile['booking_url_base']
                elif 'slug' in profile:
                    # Fallback: Erstelle die Standard-Buchungs-URL
                    speciality = profile.get('speciality_slug', 'doctor')
                    city = profile.get('city_slug', 'unknown')
                    return f"https://www.doctolib.de/{speciality}/{city}/{profile['slug']}"
        
        # Fallback auf HTML-Parsing
        return get_booking_url_html_fallback(doctor_url)
        
    except Exception as e:
        print(f"Fehler beim Abrufen der Buchungs-URL: {e}")
        return get_booking_url_html_fallback(doctor_url)

def get_booking_url_html_fallback(doctor_url):
    """
    Fallback-Methode für HTML-Parsing
    """
    try:
        request_obj = urllib.request.Request(doctor_url)
        request_obj.add_header(
            'User-Agent',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        
        response = urllib.request.urlopen(request_obj).read().decode('utf-8')
        
        # Suche nach Buchungs-Button oder -Link
        booking_patterns = [
            r'href="([^"]*book[^"]*)"',
            r'href="([^"]*booking[^"]*)"',
            r'href="([^"]*termin[^"]*)"',
            r'data-booking-url="([^"]*)"'
        ]
        
        for pattern in booking_patterns:
            booking_match = re.search(pattern, response, re.IGNORECASE)
            if booking_match:
                booking_url = booking_match.group(1)
                if not booking_url.startswith('http'):
                    booking_url = 'https://www.doctolib.de' + booking_url
                return booking_url
        
        return None
        
    except Exception as e:
        print(f"Fehler beim HTML-Parsing: {e}")
        return None

@app.route('/')
def index():
    """Hauptseite mit Suchformular"""
    specialities = get_specialities()
    return render_template('search.html', specialities=specialities)

@app.route('/search', methods=['POST'])
def search():
    """API-Endpoint für die Arztsuche - Verwendet echte Doctolib API"""
    data = request.get_json()
    location = data.get('location', '').strip()
    speciality = data.get('speciality', '').strip()
    insurance_sector = data.get('insurance_sector', 'public')
    
    if not location:
        return jsonify({'success': False, 'error': 'Bitte geben Sie einen Ort ein'})
    
    if not speciality:
        return jsonify({'success': False, 'error': 'Bitte wählen Sie eine Fachrichtung aus'})
    
    # Verwende nur die echte API - keine Mock-Daten
    result = search_doctors_by_location(location, speciality, insurance_sector)
    return jsonify(result)

def generate_realistic_mock_data(location, speciality, insurance_sector):
    """
    Generiert realistische Mock-Daten basierend auf der Eingabe
    Dies simuliert was man auf Doctolib finden würde
    """
    # Deutsche Vor- und Nachnamen für Ärzte
    first_names = [
        'Anna', 'Thomas', 'Sarah', 'Michael', 'Julia', 'Stefan', 'Christina', 
        'Daniel', 'Petra', 'Alexander', 'Katharina', 'Markus', 'Sandra', 'Andreas'
    ]
    
    last_names = [
        'Müller', 'Schmidt', 'Wagner', 'Becker', 'Schulz', 'Hoffmann', 'Schäfer',
        'Koch', 'Richter', 'Klein', 'Wolf', 'Schröder', 'Neumann', 'Schwarz'
    ]
    
    # Praxis-Namen-Templates
    practice_templates = [
        f"{speciality.capitalize()}praxis {{}}",
        "Praxis Dr. {}",
        "Medizinisches Zentrum {}",
        "{} - Privatpraxis",
        "Gemeinschaftspraxis {}"
    ]
    
    # Straßennamen
    streets = [
        'Bahnhofstraße', 'Hauptstraße', 'Münsterplatz', 'Hirschstraße', 
        'Neue Straße', 'Marktplatz', 'Königstraße', 'Friedenstraße'
    ]
    
    doctors = []
    speciality_name = get_specialities().get(speciality, speciality.capitalize())
    
    # Generiere 3-5 realistische Ärzte
    import random
    num_doctors = random.randint(3, 5)
    
    for i in range(num_doctors):
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        full_name = f"Dr. med. {first_name} {last_name}"
        
        # Erstelle Slug
        slug = f"dr-{first_name.lower()}-{last_name.lower()}"
        
        # Erstelle URL
        url = f"https://www.doctolib.de/{speciality}/{location.lower()}/{slug}"
        
        # Erstelle Praxis-Namen
        practice_name = random.choice(practice_templates).format(last_name)
        
        # Erstelle Adresse
        street = random.choice(streets)
        house_number = random.randint(1, 99)
        address = f"{street} {house_number}, {location}"
        
        # Erstelle Telefonnummer (Beispiel)
        phone = f"0{random.randint(1000, 9999)} {random.randint(100000, 999999)}"
        
        doctor = {
            'name': full_name,
            'url': url,
            'speciality': speciality,
            'slug': slug,
            'practice_name': practice_name,
            'address': address,
            'phone': phone
        }
        
        doctors.append(doctor)
    
    return {
        'success': True,
        'search_url': f'https://www.doctolib.de/search?location={location}&speciality={speciality}&insuranceSector={insurance_sector}',
        'location': location,
        'speciality': speciality,
        'insurance_sector': insurance_sector,
        'doctors': doctors,
        'total_found': len(doctors),
        'note': f'Realistische Beispieldaten für {speciality_name} in {location}'
    }

@app.route('/get_booking_url', methods=['POST'])
def get_booking_url():
    """API-Endpoint zum Abrufen der Buchungs-URL für einen Arzt"""
    data = request.get_json()
    doctor_url = data.get('doctor_url', '')
    
    if not doctor_url:
        return jsonify({'success': False, 'error': 'Doktor-URL ist erforderlich'})
    
    booking_url = get_booking_url_from_doctor_page(doctor_url)
    
    if booking_url:
        return jsonify({'success': True, 'booking_url': booking_url})
    else:
        return jsonify({'success': False, 'error': 'Buchungs-URL konnte nicht gefunden werden'})

@app.route('/test_search', methods=['POST'])
def test_search():
    """Test-Endpoint für eine echte Suche"""
    data = request.get_json()
    location = data.get('location', 'Ulm')
    speciality = data.get('speciality', 'hautarzt')
    
    try:
        result = search_doctors_by_location(location, speciality)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/test_with_static_data', methods=['POST'])
def test_with_static_data():
    """Test mit statischen Daten, um zu zeigen wie es funktionieren sollte"""
    data = request.get_json()
    location = data.get('location', 'Ulm')
    speciality = data.get('speciality', 'hautarzt')
    
    # Statische Test-Daten
    mock_doctors = [
        {
            'name': 'Dr. Med. Anna Müller',
            'url': 'https://www.doctolib.de/hautarzt/ulm/dr-anna-mueller',
            'speciality': speciality,
            'slug': 'dr-anna-mueller',
            'practice_name': 'Hautarztpraxis Müller',
            'address': 'Bahnhofstraße 15, 89073 Ulm',
            'phone': '0731 123456'
        },
        {
            'name': 'Dr. Med. Thomas Schmidt',
            'url': 'https://www.doctolib.de/hautarzt/ulm/dr-thomas-schmidt',
            'speciality': speciality,
            'slug': 'dr-thomas-schmidt',
            'practice_name': 'Dermatologie am Münster',
            'address': 'Münsterplatz 8, 89073 Ulm',
            'phone': '0731 654321'
        },
        {
            'name': 'Dr. Med. Sarah Wagner',
            'url': 'https://www.doctolib.de/hautarzt/ulm/dr-sarah-wagner',
            'speciality': speciality,
            'slug': 'dr-sarah-wagner',
            'practice_name': 'Haut- und Laserzentrum Ulm',
            'address': 'Hirschstraße 12, 89073 Ulm',
            'phone': '0731 789012'
        }
    ]
    
    return jsonify({
        'success': True,
        'search_url': f'https://www.doctolib.de/search?location={location}&speciality={speciality}&insuranceSector=public',
        'location': location,
        'speciality': speciality,
        'insurance_sector': 'public',
        'doctors': mock_doctors,
        'total_found': len(mock_doctors),
        'note': 'Dies sind Test-Daten zur Demonstration'
    })

@app.route('/test_post_api', methods=['POST'])
def test_post_api():
    """Test-Endpoint für die echte phs_proxy API"""
    data = request.get_json()
    location = data.get('location', 'München')
    speciality = data.get('speciality', 'hautarzt')
    
    try:
        # Direkte API-Anfrage mit dem funktionierenden Format
        api_url = 'https://www.doctolib.de/phs_proxy/raw?page=0'
        
        # Verwende die gleiche create_location_object Funktion
        location_data = create_location_object(location)
        
        post_data = {
            "keyword": speciality,
            "location": location_data,
            "filters": {
                "insuranceSector": "public"
            }
        }
        
        json_data = json.dumps(post_data).encode('utf-8')
        
        request_obj = urllib.request.Request(api_url, data=json_data, method='POST')
        request_obj.add_header('Content-Type', 'application/json')
        request_obj.add_header('Accept', 'application/json, text/plain, */*')
        request_obj.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        request_obj.add_header('Referer', 'https://www.doctolib.de/')
        request_obj.add_header('Origin', 'https://www.doctolib.de')
        request_obj.add_header('X-Requested-With', 'XMLHttpRequest')
        
        try:
            with urllib.request.urlopen(request_obj) as response:
                status_code = response.getcode()
                response_text = response.read().decode('utf-8')
                
                # Versuche JSON zu parsen
                try:
                    json_response = json.loads(response_text)
                    return jsonify({
                        'success': True,
                        'status_code': status_code,
                        'response_length': len(response_text),
                        'json_keys': list(json_response.keys()) if isinstance(json_response, dict) else 'Not a dict',
                        'post_data_used': post_data,
                        'location_object': location_data
                    })
                except json.JSONDecodeError:
                    return jsonify({
                        'success': True,
                        'status_code': status_code,
                        'response_length': len(response_text),
                        'response_preview': response_text[:500],
                        'post_data_used': post_data,
                        'note': 'Response ist kein gültiges JSON'
                    })
                
        except urllib.error.HTTPError as e:
            error_response = e.read().decode('utf-8') if e.fp else 'No error details'
            return jsonify({
                'success': False,
                'error': f'HTTP {e.code}: {e.reason}',
                'error_details': error_response[:500],
                'post_data_used': post_data,
                'location_object': location_data
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'post_data_used': post_data if 'post_data' in locals() else None
        })

def create_location_object(location_name):
    """
    Erstellt ein Location-Objekt im Doctolib-Format basierend auf dem Ortsnamen
    """
    # Basis-Location-Objekte für häufige deutsche Städte
    location_database = {
        "münchen": {
            "place": {
                "id": 144,
                "placeId": "ChIJ2V-Mo_l1nkcRfZixfUq4DAE",
                "name": "München",
                "nameWithPronoun": "in München ",
                "slug": "muenchen",
                "country": "de",
                "viewport": {
                    "northeast": {"lat": 48.24821969652085, "lng": 11.72287551432547},
                    "southwest": {"lat": 48.06160176222775, "lng": 11.36079598983695}
                },
                "type": "locality",
                "zipcodes": ["80331", "80333", "80335", "80336", "80337", "80339"],
                "gpsPoint": {"lat": 48.1351253, "lng": 11.5819806},
                "locality": "München",
                "streetName": None,
                "streetNumber": None
            }
        },
        "ulm": {
            "place": {
                "id": None,
                "placeId": None,
                "name": "XXX",
                "nameWithPronoun": None,
                "slug": None,
                "country": "de",
                "viewport":  None,
                "type": "locality",
                "zipcodes": None,
                "gpsPoint": {"lat": 48.3974, "lng": 9.9934},
                "locality": "XXX",
                "streetName": None,
                "streetNumber": None
            }
        },
        "berlin": {
            "place": {
                "id": 146,
                "placeId": "ChIJAVkDPzdOqEcRcDteJg8V54s",
                "name": "Berlin",
                "nameWithPronoun": "in Berlin ",
                "slug": "berlin",
                "country": "de",
                "viewport": {
                    "northeast": {"lat": 52.6755, "lng": 13.7611},
                    "southwest": {"lat": 52.3382, "lng": 13.0883}
                },
                "type": "locality",
                "zipcodes": ["10115", "10117", "10119", "10178", "10179", "10243"],
                "gpsPoint": {"lat": 52.5200, "lng": 13.4050},
                "locality": "Berlin",
                "streetName": None,
                "streetNumber": None
            }
        },
        "hamburg": {
            "place": {
                "id": 147,
                "placeId": "ChIJuRMYfoNOsUcRoDrjkHq69qs",
                "name": "Hamburg",
                "nameWithPronoun": "in Hamburg ",
                "slug": "hamburg",
                "country": "de",
                "viewport": {
                    "northeast": {"lat": 53.7499, "lng": 10.3267},
                    "southwest": {"lat": 53.3951, "lng": 9.7312}
                },
                "type": "locality",
                "zipcodes": ["20095", "20097", "20099", "20144", "20146", "20148"],
                "gpsPoint": {"lat": 53.5511, "lng": 9.9937},
                "locality": "Hamburg",
                "streetName": None,
                "streetNumber": None
            }
        }
    }
    
    # Normalisiere den Ortsnamen
    location_key = location_name.lower().strip()
    
    # Wenn wir den Ort in der Datenbank haben, verwende die echten Daten
    if location_key in location_database:
        return location_database[location_key]
    
    # Fallback: Erstelle ein generisches Location-Objekt
    return create_generic_location_object(location_name)

def get_coordinates_for_location(location_name):
    """
    Versucht GPS-Koordinaten für einen Ortsnamen oder PLZ zu ermitteln
    Verwendet verschiedene Methoden und Bibliotheken
    """
    
    # Methode 1: Mit geopy/Nominatim (OpenStreetMap)
    if GEOPY_AVAILABLE:
        try:
            import time
            geolocator = Nominatim(user_agent="doctolib_search_app")
            
            # Suche mit Deutschland-Kontext für bessere Ergebnisse
            search_query = f"{location_name}, Deutschland"
            location = geolocator.geocode(search_query, timeout=5)
            
            if location:
                lat = round(location.latitude, 6)
                lng = round(location.longitude, 6)
                print(f"DEBUG: GPS-Koordinaten für '{location_name}' via Nominatim gefunden: {lat}, {lng}")
                time.sleep(1)  # Rate limiting
                return lat, lng
            else:
                # Fallback: Versuche nur mit Stadtname
                location = geolocator.geocode(location_name, timeout=5)
                if location:
                    lat = round(location.latitude, 6)
                    lng = round(location.longitude, 6)
                    print(f"DEBUG: GPS-Koordinaten für '{location_name}' via Nominatim (Fallback) gefunden: {lat}, {lng}")
                    time.sleep(1)  # Rate limiting
                    return lat, lng
        except Exception as e:
            print(f"DEBUG: Fehler bei Nominatim-Geocoding: {e}")
    
    # Methode 2: Mit pgeocode (für deutsche Postleitzahlen)
    if PGEOCODE_AVAILABLE:
        try:
            # Prüfe ob es sich um eine deutsche PLZ handelt (5 Ziffern)
            if location_name.isdigit() and len(location_name) == 5:
                nomi = pgeocode.Nominatim('DE')
                location_info = nomi.query_postal_code(location_name)
                
                if not location_info.isna().latitude:  # Pandas NaN check
                    lat = round(float(location_info.latitude), 6)
                    lng = round(float(location_info.longitude), 6)
                    city_name = location_info.place_name
                    print(f"DEBUG: GPS-Koordinaten für PLZ '{location_name}' ({city_name}) via pgeocode gefunden: {lat}, {lng}")
                    return lat, lng
        except Exception as e:
            print(f"DEBUG: Fehler bei pgeocode-Geocoding: {e}")
    
    # Methode 3: Einfache deutsche Städte-Datenbank (häufige Städte)
    try:
        german_cities = {
            'berlin': (52.5200, 13.4050),
            'hamburg': (53.5511, 9.9937),
            'münchen': (48.1351, 11.5820),
            'köln': (50.9375, 6.9603),
            'frankfurt': (50.1109, 8.6821),
            'stuttgart': (48.7758, 9.1829),
            'düsseldorf': (51.2277, 6.7735),
            'dortmund': (51.5136, 7.4653),
            'essen': (51.4556, 7.0116),
            'leipzig': (51.3397, 12.3731),
            'bremen': (53.0793, 8.8017),
            'dresden': (51.0504, 13.7373),
            'hannover': (52.3759, 9.7320),
            'nürnberg': (49.4521, 11.0767),
            'duisburg': (51.4344, 6.7623),
            'bochum': (51.4819, 7.2162),
            'wuppertal': (51.2562, 7.1508),
            'bielefeld': (52.0302, 8.5325),
            'bonn': (50.7374, 7.0982),
            'münster': (51.9607, 7.6261),
            'karlsruhe': (49.0069, 8.4037),
            'mannheim': (49.4875, 8.4660),
            'augsburg': (48.3705, 10.8978),
            'wiesbaden': (50.0782, 8.2398),
            'gelsenkirchen': (51.5177, 7.0857),
            'mönchengladbach': (51.1805, 6.4428),
            'braunschweig': (52.2689, 10.5268),
            'chemnitz': (50.8278, 12.9214),
            'kiel': (54.3233, 10.1228),
            'aachen': (50.7753, 6.0839),
            'halle': (51.4969, 11.9695),
            'magdeburg': (52.1205, 11.6276),
            'freiburg': (47.9990, 7.8421),
            'krefeld': (51.3388, 6.5853),
            'lübeck': (53.8655, 10.6866),
            'oberhausen': (51.4963, 6.8626),
            'erfurt': (50.9848, 11.0299),
            'mainz': (49.9929, 8.2473),
            'rostock': (54.0887, 12.1402),
            'kassel': (51.3127, 9.4797),
            'hagen': (51.3670, 7.4637),
            'hamm': (51.6806, 7.8142),
            'saarbrücken': (49.2401, 6.9969),
            'mülheim': (51.4266, 6.8827),
            'potsdam': (52.3906, 13.0645),
            'ludwigshafen': (49.4774, 8.4451),
            'oldenburg': (53.1435, 8.2146),
            'leverkusen': (51.0458, 6.9888),
            'osnabrück': (52.2799, 8.0472),
            'solingen': (51.1657, 7.067),
            'heidelberg': (49.3988, 8.6724),
            'herne': (51.5386, 7.2047),
            'neuss': (51.1979, 6.6921),
            'darmstadt': (49.8728, 8.6512),
            'paderborn': (51.7189, 8.7575),
            'regensburg': (49.0134, 12.1016),
            'ingolstadt': (48.7665, 11.4257),
            'würzburg': (49.7913, 9.9534),
            'fürth': (49.4778, 10.9890),
            'wolfsburg': (52.4227, 10.7865),
            'offenbach': (50.0955, 8.7761),
            'ulm': (48.3974, 9.9934),
            'heilbronn': (49.1427, 9.2109),
            'pforzheim': (48.8915, 8.6984),
            'göttingen': (51.5412, 9.9158),
            'bottrop': (51.5216, 6.9289),
            'trier': (49.7596, 6.6441),
            'recklinghausen': (51.6142, 7.1969),
            'reutlingen': (48.4911, 9.2072),
            'bremerhaven': (53.5396, 8.5809),
            'koblenz': (50.3569, 7.5890),
            'bergisch gladbach': (50.9924, 7.1401),
            'jena': (50.9278, 11.5859),
            'remscheid': (51.1784, 7.1896),
            'erlangen': (49.5897, 11.0041),
            'moers': (51.4508, 6.6268),
            'siegen': (50.8719, 8.0243),
            'hildesheim': (52.1561, 9.9511),
            'salzgitter': (52.1533, 10.4003),
        }
        
        location_key = location_name.lower().strip()
        if location_key in german_cities:
            lat, lng = german_cities[location_key]
            print(f"DEBUG: GPS-Koordinaten für '{location_name}' aus lokaler Datenbank gefunden: {lat}, {lng}")
            return lat, lng
    except Exception as e:
        print(f"DEBUG: Fehler bei lokaler Städte-Datenbank: {e}")
    
    print(f"DEBUG: Keine GPS-Koordinaten für '{location_name}' gefunden")
    return None, None

def create_generic_location_object(location_name):
    """
    Erstellt ein generisches Location-Objekt für unbekannte Orte
    """
    
    # Versuche zuerst, echte GPS-Koordinaten zu ermitteln
    lat, lng = get_coordinates_for_location(location_name)
    
    if not lat or not lng:
        # Fallback auf zufällige deutsche Koordinaten
        lat = round(random.uniform(47.3, 54.9), 6)  # Deutschland Breitengrad
        lng = round(random.uniform(5.9, 15.0), 6)   # Deutschland Längengrad
        print(f"DEBUG: Verwende zufällige Koordinaten: {lat}, {lng}")
    
    # Erstelle Slug
    slug = location_name.lower().replace(' ', '-').replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    
    # Generiere eine zufällige ID
    place_id = random.randint(1000, 9999)
    
    return {
        "place": {
            "id": place_id,
            "placeId": f"ChIJ_generic_{place_id}",
            "name": location_name,
            "nameWithPronoun": f"in {location_name} ",
            "slug": slug,
            "country": "de",
            "viewport": {
                "northeast": {"lat": lat + 0.1, "lng": lng + 0.1},
                "southwest": {"lat": lat - 0.1, "lng": lng - 0.1}
            },
            "type": "locality",
            "zipcodes": ["00000"],
            "gpsPoint": {"lat": lat, "lng": lng},
            "locality": location_name,
            "streetName": None,
            "streetNumber": None
        }
    }

def get_doctor_availability(agenda_ids, visit_motive_id=5101729, insurance_sector='public'):
    """
    Ruft die Verfügbarkeit eines Arztes über die Doctolib-API ab
    """
    try:
        from datetime import datetime
        
        # Validiere agenda_ids
        if not agenda_ids:
            print("DEBUG: Keine agenda_ids übergeben!")
            return {
                'success': False,
                'error': 'Keine agenda_ids angegeben',
                'data': None
            }
        
        # Stelle sicher, dass agenda_ids eine Liste ist
        if not isinstance(agenda_ids, list):
            agenda_ids = [agenda_ids]
        
        print(f"DEBUG: Verwende agenda_ids: {agenda_ids}")
        
        # Heute als Startdatum
        start_date = datetime.now().strftime('%Y-%m-%d')
        
        # URL für Verfügbarkeits-API
        availability_url = 'https://www.doctolib.de/search/availabilities.json'
        
        # Parameter für die Verfügbarkeitsabfrage
        # agenda_ids müssen mit Bindestrichen getrennt werden, nicht mit Kommas
        agenda_ids_string = '-'.join(map(str, agenda_ids))
        params = {
            'telehealth': 'false',
            'limit': '3',
            'start_date': start_date,
            'visit_motive_id': str(visit_motive_id),
            'agenda_ids': agenda_ids_string,
            'insurance_sector': insurance_sector
        }
        
        # Erstelle URL mit Parametern
        param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{availability_url}?{param_string}"
        
        print(f"DEBUG: Verfügbarkeits-URL: {full_url}")
        print(f"DEBUG: agenda_ids_string: '{agenda_ids_string}'")
        
        # HTTP Request vorbereiten
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.doctolib.de/'
        }
        
        # HTTP Request
        request = urllib.request.Request(full_url, headers=headers)
        
        with urllib.request.urlopen(request, timeout=15) as response:
            response_data = response.read()
            
            # Decode mit explizitem UTF-8
            try:
                response_text = response_data.decode('utf-8')
            except UnicodeDecodeError:
                response_text = response_data.decode('latin-1')
            
            # Parse JSON
            availability_data = json.loads(response_text)
            
            print(f"DEBUG: Verfügbarkeits-API Response Keys: {list(availability_data.keys()) if isinstance(availability_data, dict) else 'Keine Dict'}")
            
            return {
                'success': True,
                'data': availability_data,
                'start_date': start_date
            }
    
    except Exception as e:
        print(f"DEBUG: Fehler beim Abrufen der Verfügbarkeiten: {e}")
        return {
            'success': False,
            'error': str(e),
            'data': None
        }

@app.route('/get_availability', methods=['POST'])
def get_availability():
    """
    Endpoint zum Abrufen der Verfügbarkeiten für einen Arzt
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Keine Daten empfangen'
            })
        
        doctor_url = data.get('doctor_url', '')
        agenda_ids = data.get('agenda_ids', [])
        visit_motive_id = data.get('visit_motive_id', 5101729)
        insurance_sector = data.get('insurance_sector', 'public')
        
        print(f"DEBUG: Empfangene Parameter - agenda_ids: {agenda_ids}, visit_motive_id: {visit_motive_id}")
        
        if not agenda_ids:
            # Versuche agenda_ids aus der Arzt-URL zu extrahieren
            if doctor_url:
                agenda_ids = extract_agenda_ids_from_url(doctor_url)
        
        if not agenda_ids:
            return jsonify({
                'success': False,
                'error': 'Keine Agenda-IDs gefunden. Bitte agenda_ids Parameter übergeben.'
            })
        
        # Hole Verfügbarkeiten
        availability_result = get_doctor_availability(agenda_ids, visit_motive_id, insurance_sector)
        
        if availability_result['success']:
            # Verarbeite die Verfügbarkeits-Daten
            processed_availability = process_availability_data(availability_result['data'])
            
            return jsonify({
                'success': True,
                'availability': processed_availability,
                'start_date': availability_result['start_date'],
                'agenda_ids': agenda_ids,
                'visit_motive_id': visit_motive_id,
                'raw_data': availability_result['data']  # Für Debugging
            })
        else:
            return jsonify({
                'success': False,
                'error': availability_result['error']
            })
    
    except Exception as e:
        print(f"Fehler beim Abrufen der Verfügbarkeiten: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })

def extract_agenda_ids_from_url(doctor_url):
    """
    Extrahiert Agenda-IDs aus einer Doctolib-Arzt-URL
    """
    try:
        if not doctor_url:
            return []
        
        # Hole die Arzt-Seite, um agenda_ids zu finden
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8'
        }
        
        request = urllib.request.Request(doctor_url, headers=headers)
        
        with urllib.request.urlopen(request, timeout=10) as response:
            html_content = response.read().decode('utf-8')
            
            # Suche nach agenda_ids im HTML
            agenda_pattern = r'agenda_ids["\']?\s*:\s*\[([^\]]+)\]'
            match = re.search(agenda_pattern, html_content)
            
            if match:
                agenda_ids_str = match.group(1)
                # Extrahiere Zahlen
                agenda_ids = re.findall(r'\d+', agenda_ids_str)
                return [int(aid) for aid in agenda_ids]
            
            # Alternative: Suche nach data-agenda-id Attributen
            agenda_attr_pattern = r'data-agenda-id["\']?\s*=\s*["\']?(\d+)'
            agenda_matches = re.findall(agenda_attr_pattern, html_content)
            
            if agenda_matches:
                return [int(aid) for aid in agenda_matches]
        
        return []
    
    except Exception as e:
        print(f"DEBUG: Fehler beim Extrahieren der Agenda-IDs: {e}")
        return []

def process_availability_data(availability_data):
    """
    Verarbeitet die rohen Verfügbarkeits-Daten in ein benutzerfreundliches Format
    """
    try:
        if not isinstance(availability_data, dict):
            return {'available_dates': [], 'total': 0, 'message': 'Keine Daten verfügbar'}
        
        # Debug: Zeige die komplette Struktur der Verfügbarkeits-Daten
        print(f"DEBUG: Verfügbarkeits-Daten Struktur: {json.dumps(availability_data, indent=2, ensure_ascii=False)}")
        print(f"DEBUG: Verfügbare Keys: {list(availability_data.keys())}")
        
        available_dates = []
        
        # Suche nach verfügbaren Terminen in verschiedenen möglichen Strukturen
        
        # 1. Verarbeite availabilities Array (wenn vorhanden)
        if 'availabilities' in availability_data:
            availabilities = availability_data['availabilities']
            print(f"DEBUG: availabilities gefunden mit {len(availabilities)} Einträgen")
            print(f"DEBUG: Komplette availabilities Struktur: {json.dumps(availabilities, indent=2, ensure_ascii=False)}")
            
            for i, availability in enumerate(availabilities):
                print(f"DEBUG: Verarbeite Verfügbarkeit #{i}: {availability}")
                
                if isinstance(availability, dict):
                    date = availability.get('date', '')
                    slots = availability.get('slots', [])
                    
                    print(f"DEBUG: Verarbeite Verfügbarkeit für Datum: '{date}' mit {len(slots)} Slots")
                    print(f"DEBUG: Slots-Inhalt: {slots}")
                    
                    if date:  # Datum ist erforderlich
                        formatted_slots = []
                        
                        # Verarbeite Slots wenn vorhanden
                        if slots:
                            for slot in slots[:5]:  # Begrenze auf 5 Termine pro Tag
                                if isinstance(slot, dict):
                                    start_time = slot.get('start_date', slot.get('time', ''))
                                    if start_time:
                                        # Extrahiere nur die Uhrzeit
                                        time_part = start_time.split('T')[-1].split('+')[0][:5]
                                        # Validiere dass es eine echte Uhrzeit ist (HH:MM Format)
                                        if ':' in time_part and len(time_part) == 5:
                                            formatted_slots.append(time_part)
                                elif isinstance(slot, str):
                                    # Direkte Zeit-Strings
                                    if 'T' in slot:
                                        time_part = slot.split('T')[-1].split('+')[0][:5]
                                        # Validiere dass es eine echte Uhrzeit ist (HH:MM Format)
                                        if ':' in time_part and len(time_part) == 5:
                                            formatted_slots.append(time_part)
                                    elif ':' in slot and len(slot) <= 8:  # Direkte Uhrzeiten wie "09:30"
                                        formatted_slots.append(slot[:5])
                        
                        # Nur hinzufügen wenn echte Uhrzeiten verfügbar sind
                        if formatted_slots:
                            # Formatiere das Datum benutzerfreundlich (DD.MM.YYYY)
                            try:
                                date_obj = datetime.strptime(date, '%Y-%m-%d')
                                formatted_date = date_obj.strftime('%d.%m.%Y')
                            except:
                                formatted_date = date  # Fallback auf ursprüngliches Format
                            
                            available_dates.append({
                                'date': date,  # Original ISO-Datum für JavaScript
                                'formatted_date': formatted_date,  # Formatiertes Datum für Anzeige
                                'slots': formatted_slots,
                                'count': len(formatted_slots)
                            })
                            print(f"DEBUG: Verfügbarer Tag hinzugefügt: {formatted_date} mit {len(formatted_slots)} Terminen: {formatted_slots}")
                        else:
                            print(f"DEBUG: Überspringe Datum {date} - keine konkreten Uhrzeiten verfügbar")
                    else:
                        print(f"DEBUG: Überspringe Verfügbarkeit ohne Datum: {availability}")
        
        # 2. Verarbeite next_slot (falls keine Termine in availabilities gefunden wurden)
        if not available_dates and 'next_slot' in availability_data:
            # next_slot Struktur - zeigt den nächsten verfügbaren Termin
            next_slot = availability_data['next_slot']
            
            print(f"DEBUG: next_slot gefunden: {json.dumps(next_slot, indent=2, ensure_ascii=False)}")
            print(f"DEBUG: next_slot Typ: {type(next_slot)}")
            print(f"DEBUG: next_slot ist leer: {not next_slot}")
            
            # Behandle sowohl Dict- als auch String-Format für next_slot
            if isinstance(next_slot, str) and next_slot:
                # next_slot ist direkt ein ISO-Datum-String
                start_date = next_slot
                
                print(f"DEBUG: start_date aus next_slot String: '{start_date}'")
                
                if start_date and 'T' in start_date:
                    # Extrahiere Datum und Zeit
                    date_part = start_date.split('T')[0]
                    time_part = start_date.split('T')[1].split('+')[0][:5]
                    
                    # Nur verarbeiten wenn eine echte Uhrzeit verfügbar ist
                    if ':' in time_part and len(time_part) == 5:
                        # Formatiere das Datum benutzerfreundlich (DD.MM.YYYY)
                        try:
                            date_obj = datetime.strptime(date_part, '%Y-%m-%d')
                            formatted_date = date_obj.strftime('%d.%m.%Y')
                        except:
                            formatted_date = date_part  # Fallback auf ursprüngliches Format
                        
                        print(f"DEBUG: Extrahiertes Datum: '{date_part}' -> Formatiert: '{formatted_date}', Zeit: '{time_part}'")
                        
                        available_dates.append({
                            'date': date_part,  # Original ISO-Datum für JavaScript
                            'formatted_date': formatted_date,  # Formatiertes Datum für Anzeige
                            'slots': [time_part],
                            'count': 1,
                            'is_next_slot': True
                        })
                        
                        print(f"DEBUG: next_slot String erfolgreich hinzugefügt: {formatted_date} um {time_part}")
                    else:
                        print(f"DEBUG: next_slot String übersprungen - keine gültige Uhrzeit: '{time_part}'")
                else:
                    print("DEBUG: Kein gültiger start_date String in next_slot oder kein Zeitstempel")
                    
            elif isinstance(next_slot, dict) and next_slot:
                # next_slot ist ein Dictionary (ursprüngliche Implementierung)
                start_date = next_slot.get('start_date', '')
                
                print(f"DEBUG: start_date aus next_slot Dict: '{start_date}'")
                
                if start_date and 'T' in start_date:
                    # Extrahiere Datum und Zeit
                    date_part = start_date.split('T')[0]
                    time_part = start_date.split('T')[1].split('+')[0][:5]
                    
                    # Nur verarbeiten wenn eine echte Uhrzeit verfügbar ist
                    if ':' in time_part and len(time_part) == 5:
                        # Formatiere das Datum benutzerfreundlich (DD.MM.YYYY)
                        try:
                            date_obj = datetime.strptime(date_part, '%Y-%m-%d')
                            formatted_date = date_obj.strftime('%d.%m.%Y')
                        except:
                            formatted_date = date_part  # Fallback auf ursprüngliches Format
                        
                        print(f"DEBUG: Extrahiertes Datum: '{date_part}' -> Formatiert: '{formatted_date}', Zeit: '{time_part}'")
                        
                        available_dates.append({
                            'date': date_part,  # Original ISO-Datum für JavaScript
                            'formatted_date': formatted_date,  # Formatiertes Datum für Anzeige
                            'slots': [time_part],
                            'count': 1,
                            'is_next_slot': True
                        })
                        
                        print(f"DEBUG: next_slot Dict erfolgreich hinzugefügt: {formatted_date} um {time_part}")
                    else:
                        print(f"DEBUG: next_slot Dict übersprungen - keine gültige Uhrzeit: '{time_part}'")
                else:
                    print("DEBUG: Kein start_date in next_slot Dict gefunden oder kein Zeitstempel")
            else:
                print(f"DEBUG: next_slot ist weder String noch Dict oder leer. Typ: {type(next_slot)}, Inhalt: {next_slot}")
        
        # 3. Fallback: Verarbeite dates Array (alternative Struktur)
        elif not available_dates and 'dates' in availability_data:
            # Alternative Struktur
            dates = availability_data['dates']
            print(f"DEBUG: dates Array gefunden mit {len(dates)} Einträgen")
            
            for date_info in dates:
                if isinstance(date_info, dict):
                    date = date_info.get('date', '')
                    times = date_info.get('times', [])
                    
                    if date and times:
                        # Filtere nur echte Uhrzeiten (HH:MM Format)
                        valid_times = []
                        for time in times[:5]:  # Begrenze auf 5 Termine
                            if isinstance(time, str) and ':' in time and len(time) <= 8:
                                valid_times.append(time[:5])  # Nur HH:MM
                        
                        # Nur hinzufügen wenn echte Uhrzeiten vorhanden sind
                        if valid_times:
                            # Formatiere das Datum benutzerfreundlich (DD.MM.YYYY)
                            try:
                                date_obj = datetime.strptime(date, '%Y-%m-%d')
                                formatted_date = date_obj.strftime('%d.%m.%Y')
                            except:
                                formatted_date = date
                            
                            available_dates.append({
                                'date': date,
                                'formatted_date': formatted_date,
                                'slots': valid_times,
                                'count': len(valid_times)
                            })
                            print(f"DEBUG: Datum aus dates Array hinzugefügt: {formatted_date} mit {len(valid_times)} Terminen")
                        else:
                            print(f"DEBUG: Datum {date} übersprungen - keine gültigen Uhrzeiten")
        
        # 4. Prüfe auch auf direkte Slots in der Hauptebene
        elif not available_dates and 'slots' in availability_data:
            slots = availability_data['slots']
            print(f"DEBUG: Direkte slots gefunden: {len(slots)}")
            
            # Gruppiere Slots nach Datum
            slots_by_date = {}
            for slot in slots:
                if isinstance(slot, dict):
                    start_date = slot.get('start_date', '')
                    if start_date and 'T' in start_date:
                        date_part = start_date.split('T')[0]
                        time_part = start_date.split('T')[1].split('+')[0][:5]
                        
                        # Nur gültige Uhrzeiten berücksichtigen
                        if ':' in time_part and len(time_part) == 5:
                            if date_part not in slots_by_date:
                                slots_by_date[date_part] = []
                            slots_by_date[date_part].append(time_part)
            
            # Konvertiere zu available_dates Format
            for date, times in slots_by_date.items():
                if times:  # Nur wenn gültige Zeiten vorhanden sind
                    try:
                        date_obj = datetime.strptime(date, '%Y-%m-%d')
                        formatted_date = date_obj.strftime('%d.%m.%Y')
                    except:
                        formatted_date = date
                    
                    available_dates.append({
                        'date': date,
                        'formatted_date': formatted_date,
                        'slots': times[:5],  # Begrenze auf 5 Termine
                        'count': len(times)
                    })
                    print(f"DEBUG: Direkte Slots hinzugefügt: {formatted_date} mit {len(times)} Terminen")
        
        result = {
            'available_dates': available_dates,
            'total': len(available_dates),
            'message': f'{len(available_dates)} verfügbare Tage gefunden' if available_dates else 'Keine Termine verfügbar'
        }
        
        print(f"DEBUG: Finales Ergebnis: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return result
    
    except Exception as e:
        print(f"DEBUG: Fehler beim Verarbeiten der Verfügbarkeits-Daten: {e}")
        traceback.print_exc()
        return {'available_dates': [], 'total': 0, 'message': 'Fehler beim Verarbeiten der Daten'}

@app.route('/test_agenda_ids', methods=['POST'])
def test_agenda_ids():
    """Test-Endpoint um agenda_ids aus der phs_proxy API zu extrahieren"""
    data = request.get_json()
    location = data.get('location', 'München')
    speciality = data.get('speciality', 'hautarzt')
    
    try:
        # Führe eine normale Suche durch
        result = search_doctors_by_location(location, speciality)
        
        if result['success'] and result['doctors']:
            agenda_info = []
            
            for doctor in result['doctors']:
                doctor_info = {
                    'name': doctor.get('name', 'Unbekannt'),
                    'agenda_ids': doctor.get('agenda_ids', []),
                    'url': doctor.get('url', ''),
                    'id': doctor.get('id', '')
                }
                agenda_info.append(doctor_info)
            
            return jsonify({
                'success': True,
                'location': location,
                'speciality': speciality,
                'total_doctors': len(result['doctors']),
                'doctors_with_agenda_ids': agenda_info,
                'agenda_ids_found': sum(1 for d in agenda_info if d['agenda_ids'])
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Keine Ärzte gefunden'),
                'location': location,
                'speciality': speciality
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'location': location,
            'speciality': speciality
        })

@app.route('/test_availability_with_agenda_ids', methods=['POST'])
def test_availability_with_agenda_ids():
    """Test-Endpoint der agenda_ids aus der Suche nutzt und damit Verfügbarkeiten abfragt"""
    data = request.get_json()
    location = data.get('location', 'Berlin')
    speciality = data.get('speciality', 'hautarzt')
    
    try:
        # Führe eine normale Suche durch um agenda_ids zu bekommen
        search_result = search_doctors_by_location(location, speciality)
        
        if not search_result['success'] or not search_result['doctors']:
            return jsonify({
                'success': False,
                'error': 'Keine Ärzte in der Suche gefunden',
                'location': location,
                'speciality': speciality
            })
        
        availability_results = []
        
        # Teste Verfügbarkeiten für die ersten 3 Ärzte mit agenda_ids
        for i, doctor in enumerate(search_result['doctors'][:3]):
            agenda_ids = doctor.get('agenda_ids', [])
            
            if not agenda_ids:
                availability_results.append({
                    'doctor_name': doctor.get('name', 'Unbekannt'),
                    'doctor_id': doctor.get('id', ''),
                    'agenda_ids': [],
                    'availability': None,
                    'error': 'Keine agenda_ids verfügbar'
                })
                continue
            
            print(f"DEBUG: Teste Verfügbarkeiten für {doctor.get('name')} mit agenda_ids: {agenda_ids}")
            
            # Verwende die visit_motive_id aus den Arztdaten oder Fallback
            visit_motive_id = doctor.get('visit_motive_id', 5101729)
            
            # Hole Verfügbarkeiten mit den extrahierten agenda_ids und visit_motive_id
            availability_result = get_doctor_availability(
                agenda_ids=agenda_ids,
                visit_motive_id=visit_motive_id,
                insurance_sector='public'
            )
            
            if availability_result['success']:
                processed_availability = process_availability_data(availability_result['data'])
                availability_results.append({
                    'doctor_name': doctor.get('name', 'Unbekannt'),
                    'doctor_id': doctor.get('id', ''),
                    'agenda_ids': agenda_ids,
                    'availability': processed_availability,
                    'start_date': availability_result['start_date']
                })
            else:
                availability_results.append({
                    'doctor_name': doctor.get('name', 'Unbekannt'),
                    'doctor_id': doctor.get('id', ''),
                    'agenda_ids': agenda_ids,
                    'availability': None,
                    'error': availability_result.get('error', 'Unbekannter Fehler')
                })
        
        return jsonify({
            'success': True,
            'location': location,
            'speciality': speciality,
            'total_doctors_searched': len(search_result['doctors']),
            'doctors_tested': len(availability_results),
            'availability_results': availability_results,
            'summary': {
                'doctors_with_agenda_ids': sum(1 for r in availability_results if r.get('agenda_ids')),
                'successful_availability_checks': sum(1 for r in availability_results if r.get('availability')),
                'failed_availability_checks': sum(1 for r in availability_results if r.get('error'))
            }
        })
        
    except Exception as e:
        print(f"Fehler beim Testen der Verfügbarkeiten: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'location': location,
            'speciality': speciality
        })

@app.route('/test_specific_availability', methods=['POST'])
def test_specific_availability():
    """Test-Endpoint für die spezifische Verfügbarkeits-URL"""
    data = request.get_json()
    
    # Verwende die Parameter aus der URL oder Defaults
    agenda_ids = data.get('agenda_ids', [1075438])
    visit_motive_id = data.get('visit_motive_id', 7357793)
    start_date = data.get('start_date', '2025-07-13')
    insurance_sector = data.get('insurance_sector', 'public')
    
    try:
        # Teste die spezifische URL
        availability_url = 'https://www.doctolib.de/search/availabilities.json'
        
        # agenda_ids müssen mit Bindestrichen getrennt werden, nicht mit Kommas
        agenda_ids_string = '-'.join(map(str, agenda_ids))
        params = {
            'telehealth': 'false',
            'limit': '3',
            'start_date': start_date,
            'visit_motive_id': str(visit_motive_id),
            'agenda_ids': agenda_ids_string,
            'insurance_sector': insurance_sector
        }
        
        param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{availability_url}?{param_string}"
        
        print(f"DEBUG: Teste URL: {full_url}")
        
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.doctolib.de/'
        }
        
        request_obj = urllib.request.Request(full_url, headers=headers)
        
        with urllib.request.urlopen(request_obj, timeout=15) as response:
            response_data = response.read()
            
            try:
                response_text = response_data.decode('utf-8')
            except UnicodeDecodeError:
                response_text = response_data.decode('latin-1')
            
            # Parse JSON
            availability_data = json.loads(response_text)
            
            print(f"DEBUG: Rohe API-Response: {json.dumps(availability_data, indent=2, ensure_ascii=False)}")
            
            # Verarbeite die Daten
            processed_availability = process_availability_data(availability_data)
            
            return jsonify({
                'success': True,
                'url_tested': full_url,
                'raw_data': availability_data,
                'processed_data': processed_availability,
                'parameters_used': params
            })
            
    except Exception as e:
        print(f"DEBUG: Fehler beim Testen der spezifischen URL: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'url_tested': full_url if 'full_url' in locals() else 'URL konnte nicht erstellt werden'
        })

@app.route('/test_specific_availability_url', methods=['POST'])
def test_specific_availability_url():
    """Test-Endpoint für die spezifische Verfügbarkeits-URL von der Frage"""
    try:
        # Die Parameter aus der spezifischen URL
        agenda_ids = [376833]
        visit_motive_id = 2368713
        start_date = '2025-07-13'
        insurance_sector = 'public'
        
        print(f"DEBUG: Teste spezifische URL mit agenda_ids: {agenda_ids}, visit_motive_id: {visit_motive_id}")
        
        # Teste die Verfügbarkeits-API direkt
        availability_result = get_doctor_availability(
            agenda_ids=agenda_ids,
            visit_motive_id=visit_motive_id,
            insurance_sector=insurance_sector
        )
        
        if availability_result['success']:
            processed_availability = process_availability_data(availability_result['data'])
            
            return jsonify({
                'success': True,
                'url_tested': f'https://www.doctolib.de/search/availabilities.json?telehealth=false&limit=3&start_date={start_date}&visit_motive_id={visit_motive_id}&agenda_ids={agenda_ids[0]}&insurance_sector={insurance_sector}',
                'raw_data': availability_result['data'],
                'processed_data': processed_availability,
                'parameters_used': {
                    'agenda_ids': agenda_ids,
                    'visit_motive_id': visit_motive_id,
                    'start_date': start_date,
                    'insurance_sector': insurance_sector
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': availability_result.get('error', 'Unbekannter Fehler'),
                'url_tested': f'https://www.doctolib.de/search/availabilities.json?telehealth=false&limit=3&start_date={start_date}&visit_motive_id={visit_motive_id}&agenda_ids={agenda_ids[0]}&insurance_sector={insurance_sector}'
            })
            
    except Exception as e:
        print(f"DEBUG: Fehler beim Testen der spezifischen URL: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })
