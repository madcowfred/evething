import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['DJANGO_SETTINGS_MODULE'] = 'evething.settings'

import djcelery
djcelery.setup_loader()

import django.core.handlers.wsgi

application = django.core.handlers.wsgi.WSGIHandler()
