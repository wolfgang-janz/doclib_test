from flask import Flask, render_template, request, jsonify
import json
import urllib.parse
import urllib.request
import re
from datetime import datetime

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
                'id': provider_data.get('id', '')
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
                "id": 145,
                "placeId": "ChIJa76xwh5SvkcRQKnGkCLCLfQ",
                "name": "Ulm",
                "nameWithPronoun": "in Ulm ",
                "slug": "ulm",
                "country": "de",
                "viewport": {
                    "northeast": {"lat": 48.4356, "lng": 10.0463},
                    "southwest": {"lat": 48.3668, "lng": 9.9234}
                },
                "type": "locality",
                "zipcodes": ["89073", "89075", "89077", "89079", "89081"],
                "gpsPoint": {"lat": 48.3974, "lng": 9.9934},
                "locality": "Ulm",
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

def create_generic_location_object(location_name):
    """
    Erstellt ein generisches Location-Objekt für unbekannte Orte
    """
    import random
    
    # Generiere eine zufällige ID und Koordinaten für Deutschland
    place_id = random.randint(1000, 9999)
    lat = round(random.uniform(47.3, 54.9), 6)  # Deutschland Breitengrad
    lng = round(random.uniform(5.9, 15.0), 6)   # Deutschland Längengrad
    
    slug = location_name.lower().replace(' ', '-').replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
