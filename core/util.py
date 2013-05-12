import datetime

from django.conf import settings
from django.core.cache import cache
from django.db.models import Max

from thing.models import APIKey

# ---------------------------------------------------------------------------

def get_minimum_keyid():
    """
    Return the minimum allowed keyid - MAX(keyid) added at least 30 minutes ago.
    """

    if not getattr(settings, 'ONLY_NEW_APIKEYS', True):
        return 0

    check_time = datetime.datetime.now() - datetime.timedelta(minutes=30)
    apikey_qs = APIKey.objects.filter(
        valid=True,
        created_at__lte=check_time,
    ).aggregate(
        m=Max('keyid'),
    )
    return apikey_qs['m']

# ---------------------------------------------------------------------------
