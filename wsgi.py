import os
import sys

# try using cdecimal for faster Decimal type
try:
    import cdecimal
except ImportError:
    pass
else:
    sys.modules["decimal"] = cdecimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['DJANGO_SETTINGS_MODULE'] = 'evething.settings'

import djcelery
djcelery.setup_loader()

import django.core.handlers.wsgi

application = django.core.handlers.wsgi.WSGIHandler()
