from datetime import date, datetime, timedelta
import json
import urllib.parse
import urllib.request

TELEGRAM_BOT_TOKEN = '8054097555:AAHWCgOOuNzC6y_D-JlYJZjx1C3H9K83j_g'
TELEGRAM_CHAT_ID = '-4904641633'
BOOKING_URL = 'https://www.doctolib.de/hautarzt/blaubeuren/gertraud-kraehn-senftleben/booking/availabilities?specialityId=1289&telehealth=false&placeId=practice-367592&insuranceSectorEnabled=true&insuranceSector=public&isNewPatient=true&isNewPatientBlocked=false&motiveIds%5B%5D=7357714&pid=practice-367592&insurance_sector=public&bookingFunnelSource=profile'
MOVE_BOOKING_URL = None
UPCOMING_DAYS = 15
MAX_DATETIME_IN_FUTURE = datetime.today() + timedelta(days = UPCOMING_DAYS)
NOTIFY_HOURLY = True

if not (
    TELEGRAM_BOT_TOKEN
    or TELEGRAM_CHAT_ID
    or BOOKING_URL
    ) or UPCOMING_DAYS > 15:
    exit()

parsed_url = urllib.parse.urlparse(BOOKING_URL)
path_parts = parsed_url.path.split('/')
doctor_name = path_parts[3]

# Extract all parameters from BOOKING_URL
booking_query = dict(urllib.parse.parse_qsl(parsed_url.query))
practice_id = booking_query.get('pid', '').replace('practice-', '')
motive_ids = booking_query.get('motiveIds[]', '')

docInfoUrl = f'https://www.doctolib.de/online_booking/api/slot_selection_funnel/v1/info.json?profile_slug={doctor_name}'
docInfoRequest = urllib.request.Request(docInfoUrl)
docInfoRequest.add_header(
    'User-Agent',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
)

docInfo = (urllib.request
           .urlopen(docInfoRequest)
           .read()
           .decode('utf-8'))

docInfoJson = json.loads(docInfo)

# Extract the doctor's name with title
doctor_name_with_title = None
first_agenda_id = None
if isinstance(docInfoJson, dict) and 'data' in docInfoJson:
    data = docInfoJson['data']
    if isinstance(data, dict) and 'profile' in data:
        profile = data['profile']
        if isinstance(profile, dict):
            doctor_name_with_title = (profile.get('name_with_title') or 
                                    profile.get('full_name') or 
                                    profile.get('name'))
    
    # Extract the first agenda ID
    if isinstance(data, dict) and 'agendas' in data:
        agendas = data['agendas']
        if isinstance(agendas, list) and len(agendas) > 0:
            first_agenda = agendas[0]
            if isinstance(first_agenda, dict) and 'id' in first_agenda:
                first_agenda_id = first_agenda['id']

if not doctor_name_with_title:
    doctor_name_with_title = doctor_name

# Construct AVAILABILITIES_URL dynamically using all extracted data
if first_agenda_id and practice_id and motive_ids:
    # Start with core parameters for availabilities API
    availabilities_params = {
        'visit_motive_ids': motive_ids,
        'agenda_ids': first_agenda_id,
        'practice_ids': practice_id
    }
    
    # Add ALL other parameters from BOOKING_URL (except the ones we already handled)
    excluded_params = {'motiveIds[]', 'pid'}  # Already handled as visit_motive_ids, agenda_ids, practice_ids
    
    for key, value in booking_query.items():
        if key not in excluded_params and value:  # Only add non-empty values
            availabilities_params[key] = value
    
    # Construct the URL
    availabilities_url = 'https://www.doctolib.de/availabilities.json?' + urllib.parse.urlencode(availabilities_params)
else:
    print("Error: Could not extract required parameters for availabilities URL")
    exit()

urlParts = urllib.parse.urlparse(availabilities_url)
query = dict(urllib.parse.parse_qsl(urlParts.query))
query.update({
    'limit': UPCOMING_DAYS,
    'start_date': date.today(),
})
newAvailabilitiesUrl = (urlParts
                            ._replace(query = urllib.parse.urlencode(query))
                            .geturl())
request = (urllib
                .request
                .Request(newAvailabilitiesUrl))
request.add_header(
    'User-Agent',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
)
response = (urllib.request
            .urlopen(request)
            .read()
            .decode('utf-8'))









availabilities = json.loads(response)

slotsInNearFuture = availabilities['total']
slotInNearFutureExist = slotsInNearFuture > 0
if slotInNearFutureExist:
    for day in availabilities['availabilities']:
        if len(day['slots']) == 0:
            continue;
        nextDatetimeIso8601 = day['date']
        nextDatetime = (datetime.fromisoformat(nextDatetimeIso8601)
                                .replace(tzinfo = None))
        if nextDatetime < MAX_DATETIME_IN_FUTURE:
            break;


message = ''

if slotInNearFutureExist:
    pluralSuffix = 's' if slotsInNearFuture > 1 else ''
    message += f'🔥 {slotsInNearFuture} slot{pluralSuffix} within {UPCOMING_DAYS}d! for {doctor_name_with_title}'
    message += '\n'
    if MOVE_BOOKING_URL:
        message += f'<a href="{MOVE_BOOKING_URL}">🚚 Move existing booking</a>.'
        message += '\n'

else:
    nextSlotDatetimeIso8601 = availabilities.get('next_slot', None)
    if not availabilities.get('next_slot'):
        message += f'❌ No slots available for {doctor_name_with_title}.'
        print(message)
        exit()
    ''' availabilities['next_slot'] '''
    nextSlotDate = (datetime.fromisoformat(nextSlotDatetimeIso8601)
                                .strftime('%d %B %Y'))
    message += f'🐌 slot <i>{nextSlotDate}</i> for <i>{doctor_name_with_title}</i>.'
    message += '\n'

message += f'Book now on <a href="{BOOKING_URL}">doctolib.de</a>.'

print(message)
"""
urlEncodedMessage = (urllib
                        .parse
                        .quote(message))


(urllib
    .request
    .urlopen(
        (f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        f'?chat_id={TELEGRAM_CHAT_ID}'
        f'&text={urlEncodedMessage}'
        f'&parse_mode=HTML'
        f'&disable_web_page_preview=true')
    ))
"""
