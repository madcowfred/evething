from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.template import RequestContext

from coffin.shortcuts import *

from thing.models import *

from thing.stuff import TimerThing

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
    jobs = jobs.select_related('character', 'corporation', 'system', 'output_item')

    # Gather some lookup ids
    char_ids = set()
    station_ids = set()
    for ij in jobs:
        char_ids.add(ij.installer_id)
        if ij.container_id > 0:
            station_ids.add(ij.container_id)

    # Bulk lookups
    char_map = Character.objects.in_bulk(char_ids)
    simple_map = SimpleCharacter.objects.in_bulk(char_ids)
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

        ij.z_installer = char_map.get(ij.installer_id, simple_map.get(ij.installer_id))
        ij.z_station = station_map.get(ij.container_id)

        if ij.completed:
            complete.append(ij)
        else:
            incomplete.append(ij)

    # Incomplete should be probably sorted in reverse order
    incomplete.sort(key=lambda j: j.end_time)

    tt.add_time('load jobs')

    # Render template
    out = render_to_response(
        'thing/industry.html',
        {
            'incomplete': incomplete,
            'complete': complete,
        },
        RequestContext(request),
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

# ---------------------------------------------------------------------------
