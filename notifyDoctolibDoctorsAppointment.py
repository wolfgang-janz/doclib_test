from datetime import date, datetime, timedelta
import json
import urllib.parse
import urllib.request

TELEGRAM_BOT_TOKEN = ''
TELEGRAM_CHAT_ID = ''
BOOKING_URL = 'https://www.doctolib.de/'
AVAILABILITIES_URL = ''
APPOINTMENT_NAME = None
MOVE_BOOKING_URL = None
UPCOMING_DAYS = 15
MAX_DATETIME_IN_FUTURE = datetime.today() + timedelta(days = UPCOMING_DAYS)
NOTIFY_HOURLY = False

if not (
    TELEGRAM_BOT_TOKEN
    or TELEGRAM_CHAT_ID
    or BOOKING_URL
    or AVAILABILITIES_URL
    ) or UPCOMING_DAYS > 15:
    exit()

urlParts = urllib.parse.urlparse(AVAILABILITIES_URL)
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
earlierSlotExists = False
if slotInNearFutureExist:
    for day in availabilities['availabilities']:
        if len(day['slots']) == 0:
            continue;
        nextDatetimeIso8601 = day['date']
        nextDatetime = (datetime.fromisoformat(nextDatetimeIso8601)
                                .replace(tzinfo = None))
        if nextDatetime < MAX_DATETIME_IN_FUTURE:
            earlierSlotExists = True
            break;

isOnTheHour = datetime.now().minute == 0
isHourlyNotificationDue = isOnTheHour and NOTIFY_HOURLY

if not (earlierSlotExists or isHourlyNotificationDue):
    exit()

message = ''
if APPOINTMENT_NAME:
    message += f'👨‍⚕️👩‍⚕️ {APPOINTMENT_NAME}'
    message += '\n'

if earlierSlotExists:
    pluralSuffix = 's' if slotsInNearFuture > 1 else ''
    message += f'🔥 {slotsInNearFuture} slot{pluralSuffix} within {UPCOMING_DAYS}d!'
    message += '\n'
    if MOVE_BOOKING_URL:
        message += f'<a href="{MOVE_BOOKING_URL}">🚚 Move existing booking</a>.'
        message += '\n'

if isHourlyNotificationDue:
    nextSlotDatetimeIso8601 = availabilities['next_slot']
    nextSlotDate = (datetime.fromisoformat(nextSlotDatetimeIso8601)
                                .strftime('%d %B %Y'))
    message += f'🐌 slot <i>{nextSlotDate}</i>.'
    message += '\n'

message += f'Book now on <a href="{BOOKING_URL}">doctolib.de</a>.'

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
