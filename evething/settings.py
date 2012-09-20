# Django settings for evething project.

import os
_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))

# admins, obviously
ADMINS = (
    ('Freddie', 'freddie@wafflemonster.org'),
)
MANAGERS = ADMINS

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = None

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(_PATH, 'tempstatic')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(_PATH, 'static'),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = ')%)w42n83ndwvlrnj99-77@e0)(kcs!$zd%#pcy0&e5x0kwq01'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    # 'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'evething.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(_PATH, 'templates'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    #'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'south',
    'djcelery',
    'mptt',
    'jinja2cache',
    'coffin',
    'thing',
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

LOGIN_REDIRECT_URL = '/'

# email address that server mails appear to be from
SERVER_EMAIL = 'evething@wafflemonster.org'

# Auth profile thing
AUTH_PROFILE_MODULE = 'thing.UserProfile'


# Themes
THEMES = [
    ('default', '<Default>'),
    ('cerulean', 'Cerulean'),
    ('cyborg', 'Cyborg'),
    ('slate', 'Slate'),
]

# Icon themes
ICON_THEMES = [
    ('default', '<Default>'),
    ('fugue-stars', 'Fugue/Stars'),
]


# load local settings
from local_settings import *
TEMPLATE_DEBUG = DEBUG


# Jinja2 cache
JINJA2_CACHE_ENABLED = True
JINJA2_CACHE_BACKEND = 'locmem://'
JINJA2_CACHE_MSTAT_DISABLED = True

# Celery setup
import djcelery
djcelery.setup_loader()

# Rename the default queue
from kombu import Exchange, Queue

# We're not using rate limits so might as well disable them to save some CPU
CELERY_DISABLE_RATE_LIMITS = True
# Set a soft task time limit of 5 minutes
CELERYD_TASK_SOFT_TIME_LIMIT = 300
# Set the prefetch multiplier to 1 so super slow tasks aren't breaking everything
CELERYD_PREFETCH_MULTIPLIER = 1
# Set up our queues
CELERY_DEFAULT_QUEUE = 'et_medium'
CELERY_QUEUES = (
    Queue('et_medium', Exchange('et_medium'), routing_key='et_medium'),
    Queue('et_high', Exchange('et_high'), routing_key='et_high'),
    Queue('et_low', Exchange('et_low'), routing_key='et_low'),
)

# Periodic tasks
from datetime import timedelta
CELERYBEAT_SCHEDULE = {
    # spawn tasks every 10 seconds
    'spawn-tasks': {
        'task': 'thing.tasks.spawn_tasks',
        'schedule': timedelta(seconds=10),
        'options': {
            'expires': 9,
            'queue': 'et_high',
        },
        'args': (),
    },

    # clean up broken tasks every 5 minutes
    'taskstate-cleanup': {
        'task': 'thing.tasks.taskstate_cleanup',
        'schedule': timedelta(minutes=5),
        'options': {
            'queue': 'et_high',
        },
        'args': (),
    },
    
    # clean up the API cache every 30 seconds
    'apicache-cleanup': {
        'task': 'thing.tasks.apicache_cleanup',
        'schedule': timedelta(seconds=30),
        'options': {
            'queue': 'et_high',
        },
        'args': (),
    },

    # update history data every 4 hours
    'history-updater': {
        'task': 'thing.tasks.history_updater',
        'schedule': timedelta(hours=4),
        'options': {
            'expires': 239 * 60,
        },
        'args': (),
    },

    # update price data every 15 minutes
    'price-updater': {
        'task': 'thing.tasks.price_updater',
        'schedule': timedelta(minutes=15),
        'options': {
            'expires': 14 * 60,
        },
        'args': (),
    },

    # update alliance list every hour
    'alliance-list': {
        'task': 'thing.tasks.alliance_list',
        'schedule': timedelta(hours=1),
        'options': {
            'expires': 59 * 60,
        },
        'args': (),
    },

    # update conquerable stations every hour
    'conquerable-stations': {
        'task': 'thing.tasks.conquerable_stations',
        'schedule': timedelta(hours=1),
        'options': {
            'expires': 59 * 60,
        },
        'args': (),
    },

    # update unknown SimpleCharacters every hour
    'fix-unknown-simplecharacters': {
        'task': 'thing.tasks.fix_unknown_simplecharacters',
        'schedule': timedelta(hours=1),
        'options': {
            'expires': 59 * 60,
        },
        'args': (),
    },
}
