import os
import sys

# try using cdecimal for faster Decimal type
try:
    import cdecimal
except ImportError:
    pass
else:
    sys.modules["decimal"] = cdecimal

#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#os.environ['DJANGO_SETTINGS_MODULE'] = 'evething.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'evething.settings')

import djcelery
djcelery.setup_loader()

#import django.core.handlers.wsgi
#application = django.core.handlers.wsgi.WSGIHandler()

# This application object is used by the development server
# as well as any WSGI server configured to use this file.
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
