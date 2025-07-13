#!/usr/bin/env python3
"""
WSGI configuration for Doctolib Search App
File: your_application.wsgi

This module contains the WSGI application used by WSGI-compatible web servers
to serve the Doctolib search application.

Usage with different WSGI servers:
    
Apache mod_wsgi:
    WSGIScriptAlias / /path/to/your_application.wsgi
    
Gunicorn:
    gunicorn --bind 0.0.0.0:8000 your_application:application
    
uWSGI:
    uwsgi --http :8000 --wsgi-file your_application.wsgi --callable application
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Import required modules
try:
    import urllib.request
    import urllib.error
    import json
    import re
    import random
    import traceback
    logging.info("Successfully imported required modules")
except ImportError as e:
    logging.error(f"Failed to import required modules: {e}")
    raise

# Import the Flask application
try:
    from search_app import app
    logging.info("Successfully imported Flask app from search_app")
except ImportError as e:
    logging.error(f"Failed to import Flask app: {e}")
    # Try alternative import methods
    try:
        sys.path.append(os.path.dirname(__file__))
        import search_app
        app = search_app.app
        logging.info("Successfully imported Flask app using alternative method")
    except Exception as e2:
        logging.error(f"Alternative import also failed: {e2}")
        raise

# WSGI application callable
application = app

# Production configuration
if not app.debug:
    # Disable debug mode for production
    app.config.update(
        DEBUG=False,
        TESTING=False,
    )
    
    # Set up file logging for production
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        'logs/your_application.log',
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Doctolib Search App startup via WSGI')

# Health check endpoint for load balancers
@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    return {'status': 'healthy', 'app': 'doctolib-search'}, 200

if __name__ == "__main__":
    # For testing the WSGI file directly
    print("Starting your_application.wsgi in test mode...")
    print("Access the app at: http://localhost:5000")
    application.run(debug=True, host='0.0.0.0', port=5000)
