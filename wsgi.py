#!/usr/bin/env python3
"""
WSGI configuration for Doctolib Search App

This module contains the WSGI application used by WSGI-compatible web servers
to serve the Doctolib search application.

Usage:
- For development: python search_app.py
- For production: Use this wsgi.py with a WSGI server like Gunicorn or uWSGI

Example with Gunicorn:
    gunicorn --bind 0.0.0.0:8000 wsgi:application
"""

import os
import sys

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Import the Flask app
from search_app import app

# WSGI application object
application = app

if __name__ == "__main__":
    # For testing the WSGI file directly
    application.run(debug=False, host='0.0.0.0', port=8000)
