from flask import Flask, render_template, request, jsonify
from datetime import date, datetime, timedelta
import json
import urllib.parse
import urllib.request

app = Flask(__name__)

def check_appointments(booking_url, upcoming_days=15):
    """
    Check for available appointments using the booking URL
    """
    try:
        # Parse the booking URL
        parsed_url = urllib.parse.urlparse(booking_url)
        path_parts = parsed_url.path.split('/')
        doctor_name = path_parts[3]
        '''OR pid place_id'''
        # Extract all parameters from BOOKING_URL
        booking_query = dict(urllib.parse.parse_qsl(parsed_url.query))
        practice_id = booking_query.get('pid', '')
        if not practice_id:
            practice_id = booking_query.get('place_id', '')
        practice_id = practice_id.replace('practice-', '')
        insurence_sector = booking_query.get('insuranceSector', '').replace('insurance_sector-', '') 
        motive_ids = booking_query.get('motiveIds[]', '')
                
        # Get doctor info
        doc_info_url = f'https://www.doctolib.de/online_booking/api/slot_selection_funnel/v1/info.json?profile_slug={doctor_name}'
        doc_info_request = urllib.request.Request(doc_info_url)
        doc_info_request.add_header(
            'User-Agent',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        )
        
        doc_info = urllib.request.urlopen(doc_info_request).read().decode('utf-8')
        doc_info_json = json.loads(doc_info)
        
        # Extract doctor's name and first agenda ID
        doctor_name_with_title = None
        first_agenda_id = None
        
        if isinstance(doc_info_json, dict) and 'data' in doc_info_json:
            data = doc_info_json['data']
            if isinstance(data, dict) and 'profile' in data:
                profile = data['profile']
                if isinstance(profile, dict):
                    doctor_name_with_title = (profile.get('name_with_title') or 
                                            profile.get('full_name') or 
                                            profile.get('name'))
            
            # Extract the correct agenda ID for the practice
            if isinstance(data, dict) and 'agendas' in data:
                agendas = data['agendas']
                print(f"DEBUG: Found {len(agendas)} agendas:")
                for i, agenda in enumerate(agendas):
                    if isinstance(agenda, dict):
                        print(f"  Agenda {i}: id={agenda.get('id')}, practice_id={agenda.get('practice_id')}")
                
                # Find agenda that matches the practice_id from the booking URL
                matching_agenda = None
                for agenda in agendas:
                    if isinstance(agenda, dict) and str(agenda.get('practice_id')) == practice_id:
                        matching_agenda = agenda
                        break
                
                if matching_agenda:
                    first_agenda_id = matching_agenda['id']
                    print(f"DEBUG: Using matching agenda_id: {first_agenda_id} for practice_id: {practice_id}")
                elif isinstance(agendas, list) and len(agendas) > 0:
                    # Fallback to first agenda if no match found
                    first_agenda = agendas[0]
                    if isinstance(first_agenda, dict) and 'id' in first_agenda:
                        first_agenda_id = first_agenda['id']
                        print(f"DEBUG: No matching practice_id found, using first agenda_id: {first_agenda_id}")
        
        if not doctor_name_with_title:
            doctor_name_with_title = doctor_name
            
        # Construct AVAILABILITIES_URL dynamically
        if not (first_agenda_id and motive_ids):
            print(f"DEBUG: {first_agenda_id} {motive_ids}")
            return {
                'error': 'Could not extract required parameters from booking URL',
                'doctor_name': doctor_name_with_title
            }
        
        # Start with core parameters for availabilities API
        availabilities_params = {
            'visit_motive_ids': motive_ids,
            'insurance_sector': insurence_sector,
            'agenda_ids': first_agenda_id            
        }
        
        # Add ALL other parameters from BOOKING_URL (except the ones we already handled)
        excluded_params = {'motiveIds[]', 'insuranceSector'}
        
        for key, value in booking_query.items():
            if key not in excluded_params and value:
                availabilities_params[key] = value
        
        # Add date and limit parameters
        availabilities_params.update({
            'limit': upcoming_days,
            'start_date': date.today().isoformat(),
        })
        
        # Construct the URL
        availabilities_url = 'https://www.doctolib.de/availabilities.json?' + urllib.parse.urlencode(availabilities_params)
        
        print(f"DEBUG: Constructed availabilities URL: {availabilities_url}")

        # Make the request
        request_obj = urllib.request.Request(availabilities_url)
        request_obj.add_header(
            'User-Agent',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        )
        
        response = urllib.request.urlopen(request_obj).read().decode('utf-8')
        availabilities = json.loads(response)
        
        # Process results
        slots_in_near_future = availabilities['total']
        slot_in_near_future_exist = slots_in_near_future > 0
        
        max_datetime_in_future = datetime.today() + timedelta(days=upcoming_days)
        next_slot_date = None
        
        if slot_in_near_future_exist:
            for day in availabilities['availabilities']:
                if len(day['slots']) == 0:
                    continue
                next_datetime_iso8601 = day['date']
                next_datetime = datetime.fromisoformat(next_datetime_iso8601).replace(tzinfo=None)
                if next_datetime < max_datetime_in_future:
                    next_slot_date = next_datetime.strftime('%d %B %Y')
                    break
        else:
            next_slot_datetime_iso8601 = availabilities.get('next_slot', None)
            if next_slot_datetime_iso8601:
                next_slot_date = datetime.fromisoformat(next_slot_datetime_iso8601).strftime('%d %B %Y')
        
        # Debug logging
        print(f"DEBUG: slots_in_near_future = {slots_in_near_future}")
        print(f"DEBUG: slot_in_near_future_exist = {slot_in_near_future_exist}")
        print(f"DEBUG: next_slot_date = {next_slot_date}")
        print(f"DEBUG: availabilities.get('next_slot') = {availabilities.get('next_slot')}")
        
        return {
            'doctor_name': doctor_name_with_title,
            'slots_count': slots_in_near_future,
            'slots_available': slot_in_near_future_exist,
            'next_slot_date': next_slot_date,
            'upcoming_days': upcoming_days,
            'booking_url': booking_url
        }
        
    except Exception as e:
        return {
            'error': f'Error checking appointments: {str(e)}'
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check():
    data = request.get_json()
    booking_url = data.get('booking_url', '')
    upcoming_days = data.get('upcoming_days', 15)
    
    if not booking_url:
        return jsonify({'error': 'Please provide a booking URL'})
    
    result = check_appointments(booking_url, upcoming_days)
    return jsonify(result)

@app.route('/notify', methods=['POST'])
def create_notification():
    """
    Create a notification for appointment availability
    """
    data = request.get_json()
    booking_url = data.get('booking_url', '')
    doctor_name = data.get('doctor_name', 'Unknown Doctor')
    
    # For now, just log a dummy line to the console
    print(f"🔔 NOTIFICATION CREATED: User wants to be notified for {doctor_name}")
    print(f"   Booking URL: {booking_url}")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return jsonify({
        'success': True,
        'message': f'Notification created for {doctor_name}. You will be notified when slots become available.'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
