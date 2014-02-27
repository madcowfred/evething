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
import operator

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count, Max, Min, Sum

from thing.models import *
from thing.stuff import *
from thing.templatetags.thing_extras import commas, duration, shortduration


from django.http import HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
import json

# ---------------------------------------------------------------------------

ONE_DAY = 24 * 60 * 60
EXPIRE_WARNING = 10 * ONE_DAY

# ---------------------------------------------------------------------------
# Home page
@login_required
def home(request):
    # We will be splitting the home page up into multiple
    # JSON Deliverable components, so this method will just
    # return the template
    return render_page('thing/home.html', {}, request)


#TODO: Caching

@login_required
def __characters(request, out):
    profile = request.user.get_profile()

    # Make a set of characters to hide
    hide_characters = set(int(c) for c in profile.home_hide_characters.split(',') if c)

    characters = Character.objects.filter(
        apikeys__user=request.user,
        apikeys__valid=True,
        apikeys__key_type__in=(APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE)
    ).exclude(
        pk__in=hide_characters
    ).prefetch_related(
        'apikeys',
    ).select_related(
        'config',
    ).distinct()

    limit_to = request.REQUEST.get('characters', None)
    if limit_to:
        limit_to = [int(c) for c in limit_to.split(',')]

    corporation_ids = set()

    for char in characters:
        if limit_to:
            if char.pk not in limit_to: continue

        if char.pk not in out['characters'].keys():
            out['characters'][char.pk] = {}

        out['characters'][char.pk]['id'] = char.pk
        out['characters'][char.pk]['name'] = char.name
        out['characters'][char.pk]['corporation'] = char.corporation_id

        out['characters'][char.pk]['apikey'] = {}
        for key, value in vars(char.apikeys.all()[0]).items():
            if key.startswith('_'): continue
            if key == 'vcode': continue
            out['characters'][char.pk]['apikey'][key] = value


        if char.corporation_id not in out['corporations'].keys():
            out['corporations'][char.corporation_id] = {}

        corporation_ids.add(char.corporation_id)

        if 'config' not in out['characters'][char.pk]:
            out['characters'][char.pk]['config'] = {}
        for key, value in vars(char.config).items():
            if key.startswith('_'): continue
            if key == 'character_id': continue

            out['characters'][char.pk]['config'][key] = value

    return out


def __details(request, out):
    details =  CharacterDetails.objects.filter(pk__in=out['characters'].keys())

    ship_item_ids = set()

    for detail in details:
        if 'details' not in out['characters'][detail.pk]:
            out['characters'][detail.pk]['details'] = {}

        if detail.ship_item_id is not None:
            ship_item_ids.add(detail.ship_item_id)

        for key, value in vars(detail).items():
            if key.startswith('_'): continue
            if key == 'character_id': continue

            out['characters'][detail.pk]['details'][key] = value

    out['ships'] = {pk: ship.name for pk, ship in Item.objects.in_bulk(ship_item_ids).items()}

    # Fetch skill data now WITHOUT Unpublished SP
    cskill_qs = CharacterSkill.objects.filter(
        character__in=out['characters'].keys(),
        skill__item__market_group__isnull=False,
    ).values(
        'character',
    ).annotate(
        total_sp=Sum('points'),
    )
    for cskill in cskill_qs:
        out['characters'][cskill['character']]['details']['total_sp'] = cskill['total_sp']

    return out

def __skill_queues(request, out):
    now = datetime.datetime.utcnow()

    offset = now - datetime.datetime.now()

    # Do skill training check - this can't be in the model because it
    # scales like crap doing individual queries
    skill_qs = []

    skill_queues = SkillQueue.objects.filter(
        character__in=out['characters'].keys(),
        end_time__gte=datetime.datetime.now()
    ).select_related('skill__item')

    for skill_queue in skill_queues:
        if 'skill_queue' not in out['characters'][skill_queue.character_id].keys():
            out['characters'][skill_queue.character_id]['skill_queue'] = []
            out['characters'][skill_queue.character_id]['skill_queue_duration'] = 0

        duration = total_seconds((skill_queue.end_time + offset) - now)

        item = {}
        for key, value in vars(skill_queue).items():
            if key.startswith('_'): continue
            if key == 'character_id': continue
            item[key] = value

        item['start_time'] = item['start_time'] + offset
        item['end_time'] = item['end_time'] + offset

        del item['skill_id']
        item['skill'] = {
            'primary_attribute': Skill.ATTRIBUTE_MAP[skill_queue.skill.primary_attribute],
            'secondary_attribute': Skill.ATTRIBUTE_MAP[skill_queue.skill.secondary_attribute],
            'name': skill_queue.skill.item.name,
            'description': skill_queue.skill.description,
            'rank': skill_queue.skill.rank,
            'html': skill_queue.skill.__html__(),
            'id': skill_queue.skill.item.pk
        }

        item['duration'] = duration

        out['characters'][skill_queue.character_id]['skill_queue'].append(item)
        out['characters'][skill_queue.character_id]['skill_queue_duration'] += duration

        skill_qs.append(Q(character=skill_queue.character_id, skill=skill_queue.skill))

    return out

def __corporations(request, out):
    for corp in Corporation.objects.filter(pk__in=out['corporations'].keys()):
        out['corporations'][corp.pk] = {}
        out['corporations'][corp.pk]['id'] = corp.pk
        out['corporations'][corp.pk]['name'] = corp.name
        out['corporations'][corp.pk]['alliance'] = corp.alliance_id

        if corp.alliance_id and (corp.alliance_id not in out['alliances'].keys()):
            out['alliances'][corp.alliance_id] = {}

    return out

def __alliances(request, out):
    for alliance in Alliance.objects.filter(pk__in=out['alliances'].keys()):
        out['alliances'][alliance.pk] = {}
        out['alliances'][alliance.pk]['id'] = alliance.pk
        out['alliances'][alliance.pk]['name'] = alliance.name

    return out

def __event_log(request, out):
    out['events'] = []
    for event in Event.objects.filter(user=request.user)[:10]:
        item = {}
        item['issued'] = event.issued
        item['text'] = event.text

        out['events'].append(item)

    return out

def __summary(request, out):
    out['summary'] = {}

    # Try retrieving total asset value from cache
    cache_key = 'home:total_assets:%d' % (request.user.id)
    total_assets = cache.get(cache_key)
    # Not cached, fetch from database and cache
    if total_assets is None:
        total_assets = AssetSummary.objects.filter(
            character__in=out['characters'].keys(),
            corporation_id=0,
        ).aggregate(
            t=Sum('total_value'),
        )['t']
        cache.set(cache_key, total_assets, 300)

    out['summary']['total_assets'] = total_assets

    return out


ALL_OPTIONS = OrderedDict([
    ('characters', __characters),
    ('details', __details),
    ('skill_queues', __skill_queues),

    ('corporations', __corporations),
    ('alliances', __alliances),
    
    ('event_log', __event_log),
    ('summary', __summary),
])

@login_required
def home_api(request):
    tt = TimerThing('home')

    request_options = request.REQUEST.getlist('options')

    out = {}
    out['characters'] = {}
    out['corporations'] = {}
    out['alliances'] = {}


    char_ids = request.REQUEST.getlist('characters')
    if char_ids:
        for id in char_ids.split(','):
            out['characters'][int(id)] = {}

    corp_ids = request.REQUEST.getlist('corporations')
    if corp_ids:
        for id in corp_ids.split(','):
            out['corporations'][int(id)] = {}

    alliance_ids = request.REQUEST.getlist('alliances')
    if alliance_ids:
        for id in alliance_ids.split(','):
            out['alliances'][int(id)] = {}

    tt.add_time('prep')

    for opt in ALL_OPTIONS.keys():
        if opt in request_options:
            out = ALL_OPTIONS[opt](request, out)
            tt.add_time(opt)

    if settings.DEBUG:
        tt.finished()

    return HttpResponse(content=json.dumps(out, cls=DjangoJSONEncoder), content_type='application/json')
