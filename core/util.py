# ------------------------------------------------------------------------------
# Copyright (c) 2010-2013, EVEthing team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     Redistributions of source code must retain the above copyright notice, this
#       list of conditions and the following disclaimer.
#     Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
# ------------------------------------------------------------------------------

import datetime
import json

from django.conf import settings
from django.core.cache import cache
from django.db.models import Max
from django.http import HttpResponse

# ---------------------------------------------------------------------------

def get_minimum_keyid():
    """
    Return the minimum allowed keyid - MAX(keyid) added at least 30 minutes ago.
    """

    from thing.models import APIKey

    if not getattr(settings, 'ONLY_NEW_APIKEYS', True):
        return 0

    minimum_keyid = cache.get('minimum_keyid')
    if minimum_keyid is None:
        check_time = datetime.datetime.now() - datetime.timedelta(minutes=30)
        apikey_qs = APIKey.objects.filter(
            valid=True,
            created_at__lte=check_time,
        ).aggregate(
            m=Max('keyid'),
        )
        minimum_keyid = apikey_qs['m']
        cache.set('minimum_keyid', minimum_keyid, 60)

    return minimum_keyid

# ---------------------------------------------------------------------------
# Convert a datetime.timedelta object into a number of seconds
def total_seconds(delta):
    return (delta.days * 24 * 60 * 60) + delta.seconds

# ------------------------------------------------------------------------------

def json_response(data):
    """
    Returns a JSON response containing data.
    """
    return HttpResponse(json.dumps(data), content_type='application/json')

# ------------------------------------------------------------------------------
