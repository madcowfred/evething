import os
import settings

# switch this to True if you want to see crash information
# NEVER LEAVE THIS ON FOR A PUBLIC SITE
DEBUG = True

# If you keep DEBUG set to False you will need to set allowed hosts correctly.
# https://docs.djangoproject.com/en/1.5/ref/settings/#std%3asetting-ALLOWED_HOSTS
ALLOWED_HOSTS = [os.environ.get('DJANGO_PORT_8000_TCP_ADDR'), '127.0.0.1']

# this is used for a few random things, it's a pretty good idea to change it
# http://www.miniwebtool.com/django-secret-key-generator/
# SECRET_KEY = ""

# these people will get e-mails with traceback information
ADMINS = (
    #('Freddie', 'freddie@wafflemonster.org'),
)

# database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',  # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'evething',                       # Or path to database file if using sqlite3.
        'USER': 'evething',                       # Not used with sqlite3.
        'PASSWORD': 'evething',                   # Not used with sqlite3.
        'HOST': os.environ.get('DB_PORT_5432_TCP_ADDR'), # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                       # Set to empty string for default. Not used with sqlite3.
    },
    # this database should contain a current version of the Static Data Export
    'import': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'sqlite-latest.sqlite',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    },
}

# change this to the public facing directory for static files, needed for
# './manage.py collectstatic' to work
STATIC_ROOT = '/evething-static'
# override the default '/static/' for static files
#STATIC_URL = 'http://static.evething.home'

# API host to use, change this if you have an API proxy handy
API_HOST = 'https://api.eveonline.com'
# Number of _permanent_ API key failures per 7 days to trigger punishment,
# 0 to disable
API_FAILURE_LIMIT = 3

# IP addresses that will see some extra DEBUG info
INTERNAL_IPS = (
    '127.0.0.1',
    '192.168.59.3'
)

# Disable the password tab if you are using external auth
DISABLE_ACCOUNT_PASSWORD = False

# Reject new API keys where keyid < MAX(keyid) added at least half an hour ago.
ONLY_NEW_APIKEYS = True

# Allow new users to register
ALLOW_REGISTRATION = False

# Default stagger APITask calls on startup
STAGGER_APITASK_STARTUP = True

# Market Data URL for prices
# - works on both eve-central or goonmetrics.
# PRICE_URL = 'http://api.eve-central.com/api/marketstat/?station_id=60003760&typeid=%s'
PRICE_URL = 'http://goonmetrics.com/api/price_data/?station_id=60003760&type_id=%s'

# Celery broker URL - http://docs.celeryproject.org/en/latest/getting-started/first-steps-with-celery.html#choosing-a-broker
BROKER_URL = 'redis://%s/0' % os.environ.get('REDIS_1_PORT_6379_TCP_ADDR')

# https://docs.djangoproject.com/en/dev/topics/cache/
# django-redis config
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        "LOCATION": 'redis://%s/1' % os.environ.get('REDIS_1_PORT_6379_TCP_ADDR'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 25}
        },
        'KEY_PREFIX': 'dj'
    }
}
# Use redis as the session handler
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
