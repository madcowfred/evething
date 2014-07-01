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

from celery import task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

from django.db import connections
from django.db.models import Count

from thing.models import APIKey, Event


@task(name='thing.purge_api_key')
def purge_api_key(apikey_id):
    """Periodic task to perform database table cleanup"""
    try:
        apikey = APIKey.objects.get(pk=apikey_id)
    except APIKey.DoesNotExist:
        logger.error('[purge_data] Invalid APIKey id %s', apikey_id)
        return

    now = datetime.datetime.now()

    # Account/Character keys
    new_events = []
    if apikey.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
        # Get the characters for this key along with a count of related APIKeys
        for char in apikey.characters.annotate(key_count=Count('apikeys')):
            # Only 1 key references this character, exterminate
            if char.key_count == 1:
                text = "All data for character '%s' has been purged" % (char.name)

                cursor = connections['default'].cursor()

                cursor.execute('DELETE FROM thing_characterconfig WHERE character_id = %s', [char.id])
                cursor.execute('DELETE FROM thing_characterdetails WHERE character_id = %s', [char.id])
                cursor.execute('DELETE FROM thing_characterskill WHERE character_id = %s', [char.id])
                cursor.execute('DELETE FROM thing_corporationstanding WHERE character_id = %s', [char.id])
                cursor.execute('DELETE FROM thing_factionstanding WHERE character_id = %s', [char.id])
                cursor.execute('DELETE FROM thing_skillqueue WHERE character_id = %s', [char.id])

                cursor.execute('DELETE FROM thing_asset WHERE character_id = %s AND corporation_id IS NULL', [char.id])
                cursor.execute('DELETE FROM thing_contract WHERE character_id = %s AND corporation_id IS NULL', [char.id])
                cursor.execute('DELETE FROM thing_industryjob WHERE character_id = %s AND corporation_id IS NULL', [char.id])

                cursor.execute('DELETE FROM thing_journalentry WHERE character_id = %s AND corp_wallet_id IS NULL', [char.id])
                cursor.execute('DELETE FROM thing_marketorder WHERE character_id = %s AND corp_wallet_id IS NULL', [char.id])
                cursor.execute('DELETE FROM thing_transaction WHERE character_id = %s AND corp_wallet_id IS NULL', [char.id])

                cursor.close()

            else:
                text = "Data for character '%s' was not purged because other valid API keys still exist" % (char.name)

            apikey.characters.remove(char)

            new_events.append(Event(
                user_id=apikey.user_id,
                issued=now,
                text=text,
            ))

        text = 'Data for your API key #%d was purged successfully.' % (apikey.id)
        new_events.append(Event(
            user_id=apikey.user_id,
            issued=now,
            text=text,
        ))

        # Delete the API key
        apikey.delete()

    if new_events:
        Event.objects.bulk_create(new_events)

# ---------------------------------------------------------------------------
