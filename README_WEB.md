# Doctolib Appointment Checker - Web Frontend

A minimalistic web frontend for checking Doctolib doctor appointments.

## Features

- ✅ Enter any Doctolib booking URL
- ✅ Check availability for the next 1-30 days
- ✅ Beautiful, responsive web interface
- ✅ Real-time appointment checking
- ✅ Works with any doctor on Doctolib

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the web application:
```bash
python app.py
```

3. Open your browser and go to:
```
http://localhost:5000
```

## How to use

1. Go to doctolib.de and find your doctor
2. Click "Book an appointment" 
3. Copy the URL from your browser's address bar
4. Paste it into the web interface
5. Click "Check Appointments"

## Files

- `app.py` - Flask web application
- `templates/index.html` - Web interface
- `notifyDoctolibDoctorsAppointment.py` - Original script
- `requirements.txt` - Python dependencies

## API Endpoint

You can also use the API directly:

```bash
curl -X POST http://localhost:5000/check \
  -H "Content-Type: application/json" \
  -d '{"booking_url": "https://www.doctolib.de/...", "upcoming_days": 15}'
```
