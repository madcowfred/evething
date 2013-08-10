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

from django.conf import settings
from django.contrib.auth.decorators import login_required

from thing.models import *
from thing.stuff import *

# ---------------------------------------------------------------------------
# Industry jobs list
@login_required
def industry(request):
    tt = TimerThing('industry')

    # Fetch valid characters/corporations for this user
    characters = Character.objects.filter(apikeys__user=request.user.id)
    character_ids = [c.id for c in characters]

    corporations = Corporation.objects.filter(pk__in=APIKey.objects.filter(user=request.user).exclude(corp_character=None).values('corp_character__corporation'))
    corporation_ids = [c.id for c in corporations]

    tt.add_time('init')

    # Fetch industry jobs for this user
    jobs = IndustryJob.objects.filter(
        Q(character__in=character_ids, corporation=None)
        |
        Q(corporation__in=corporation_ids)
    )
    jobs = jobs.prefetch_related('character', 'corporation', 'system', 'output_item')

    # Gather some lookup ids
    char_ids = set()
    station_ids = set()
    for ij in jobs:
        char_ids.add(ij.installer_id)
        if ij.container_id > 0:
            station_ids.add(ij.container_id)

    # Bulk lookups
    char_map = Character.objects.in_bulk(char_ids)
    station_map = Station.objects.in_bulk(station_ids)

    # Split into incomplete/complete
    utcnow = datetime.datetime.utcnow()

    incomplete = []
    complete = []
    for ij in jobs:
        if ij.end_time < utcnow:
            ij.z_ready = True

        ij.z_units = ij.runs * ij.output_item.portion_size

        if ij.installer_id in character_ids:
            ij.z_installer_mine = True

        ij.z_installer = char_map.get(ij.installer_id)
        ij.z_station = station_map.get(ij.container_id)

        if ij.completed:
            complete.append(ij)
        else:
            incomplete.append(ij)

    # Incomplete should be probably sorted in reverse order
    incomplete.sort(key=lambda j: j.end_time)

    tt.add_time('load jobs')

    # Render template
    out = render_page(
        'thing/industry.html',
        {
            'incomplete': incomplete,
            'complete': complete,
        },
        request,
        character_ids,
        corporation_ids,
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

# ---------------------------------------------------------------------------
