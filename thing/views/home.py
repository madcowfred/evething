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

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum

from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8


from django.http import HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
import json


# ---------------------------------------------------------------------------

ONE_DAY = 24 * 60 * 60
EXPIRE_WARNING = 10 * ONE_DAY


@login_required
def home(request):
    """Home page"""
    # We will be splitting the home page up into multiple
    # JSON Deliverable components, so this method will just
    # return the template
    return render_page(
        'thing/home.html',
        {
            'home_page_update_delay': json.dumps(
                settings.HOME_PAGE_UPDATE_DELAY
            )
        },
        request
    )


@login_required
def __characters(request, out, known):
    profile = request.user.get_profile()

    # Make a set of characters to hide
    hide_characters = set(
        int(c) for c in profile.home_hide_characters.split(',') if c
    )

    characters = None

    # We need to cache a list of all of the users characters we know about
    # so that we can attempt to load them from the cache in a moment
    cached_char_list_key = 'home:characters:%d' % (request.user.id,)
    cached_char_list = cache.get(cached_char_list_key, [])

    # keep an unalterd copy of the list for recaching later
    cached_char_list_unaltered = cached_char_list

    cached_char_key_base = 'home:character:%d'

    cached_chars = {}

    # In case we are only doing a partial update, prune out the
    # additional characters
    if out['characters']:
        cached_char_list = list(
            set(cached_char_list).intersection(out['characters'].keys())
        )

    # Try and retreived chached character information
    if cached_char_list:
        for i in cached_char_list:
            c = cache.get(cached_char_key_base % (i,))
            if c:
                cached_chars[i] = c

    if out['characters']:
        characters = Character.objects.filter(
            pk__in=out['characters'].keys(),

            apikeys__user=request.user,
            apikeys__valid=True,
            apikeys__key_type__in=(APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE)
        ).exclude(
            pk__in=cached_chars.keys()
        )
    else:
        characters = Character.objects.filter(
            apikeys__user=request.user,
            apikeys__valid=True,
            apikeys__key_type__in=(APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE)
        ).exclude(
            pk__in=list(hide_characters)+cached_chars.keys()
        )

    characters.prefetch_related(
        'apikeys',
    ).select_related(
        'config',
        'details'
    ).distinct()

    corporation_ids = set()
    ship_item_ids = set()
    system_names = set()

    out['characters'] = {}

    for char in characters:
        if char.pk in hide_characters:
            continue

        if char.pk not in out['characters'].keys():
            out['characters'][char.pk] = {}

        out['characters'][char.pk]['id'] = char.pk
        out['characters'][char.pk]['name'] = char.name
        out['characters'][char.pk]['corporation'] = char.corporation_id

        out['characters'][char.pk]['apikey'] = {}
        for key, value in vars(char.apikeys.all()[0]).items():
            if key.startswith('_'):
                continue
            if key == 'vcode':
                continue
            out['characters'][char.pk]['apikey'][key] = value

        if char.corporation_id not in out['corporations'].keys():
            out['corporations'][char.corporation_id] = {}

        corporation_ids.add(char.corporation_id)

        if 'config' not in out['characters'][char.pk]:
            out['characters'][char.pk]['config'] = {}
        for key, value in vars(char.config).items():
            if key.startswith('_'):
                continue
            if key == 'character_id':
                continue

            out['characters'][char.pk]['config'][key] = value

        if 'details' not in out['characters'][char.pk]:
            out['characters'][char.pk]['details'] = {}
        if char.details.ship_item_id is not None:
            ship_item_ids.add(char.details.ship_item_id)
        if char.details.last_known_location is not None:
            system_names.add(char.details.last_known_location)
        for key, value in vars(char.details).items():
            if key.startswith('_'):
                continue
            if key == 'character_id':
                continue

            out['characters'][char.pk]['details'][key] = value

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
        out['characters'][cskill['character']]['details']['total_sp'] = \
            cskill['total_sp']

    # and finaly add in all the characters we puulled out of the cache earleir
    for char_id, char in cached_chars.items():
        out['characters'][char_id] = char

        if 'details' in char.keys():
            ship_item_ids.add(char['details']['ship_item_id'])


    out['ships'] = {
        pk: ship.name for pk, ship in
        Item.objects.in_bulk(
            set(ship_item_ids) - set([int(s) for s in known['ships']])
        ).items()
    }

    out['systems'] = {
        name: {'constellation': '', 'region': ''} for name in system_names
    }

    # #########
    # And now Caching
    # #########
    # Cache all of the character ids that we know of for this user.
    cache.set(
        cached_char_list_key,
        list(set(cached_char_list_unaltered).union(out['characters'].keys())),
        300
    )

    # And now cache all the individual characters
    for char_id, char in out['characters'].items():
        cache.set(
            cached_char_key_base % (char['id'], ),
            char,
            300
        )

    return out


def __skill_queues(request, out, known):
    now = datetime.datetime.utcnow()

    # Do skill training check - this can't be in the model because it
    # scales like crap doing individual queries
    skill_qs = []

    skill_queues = SkillQueue.objects.filter(
        character__in=out['characters'].keys(),
        end_time__gte=datetime.datetime.now()
    ).select_related('skill__item')

    for skill_queue in skill_queues:
        # Because PEP8 hates long lines
        char_id = skill_queue.character_id

        if 'skill_queue' not in out['characters'][char_id].keys():
            out['characters'][char_id]['skill_queue'] = []
            out['characters'][char_id]['skill_queue_duration'] = 0

        duration = total_seconds(skill_queue.end_time - now)

        item = {}
        for key, value in vars(skill_queue).items():
            if key.startswith('_'):
                continue
            if key == 'character_id':
                continue
            item[key] = value

        item['start_time'] = item['start_time']
        item['end_time'] = item['end_time']

        del item['skill_id']
        item['skill'] = {
            'primary_attribute':
                Skill.ATTRIBUTE_MAP[skill_queue.skill.primary_attribute],
            'secondary_attribute':
                Skill.ATTRIBUTE_MAP[skill_queue.skill.secondary_attribute],
            'name': skill_queue.skill.item.name,
            'description': skill_queue.skill.description,
            'rank': skill_queue.skill.rank,
            'html': skill_queue.skill.__html__(),
            'id': skill_queue.skill.item.pk
        }

        item['duration'] = duration

        out['characters'][char_id]['skill_queue'].append(item)
        out['characters'][char_id]['skill_queue_duration'] += duration

        skill_qs.append(Q(character=char_id, skill=skill_queue.skill))

    return out


def __corporations(request, out, known):
    corps = set(out['corporations'].keys()) - \
        set([int(c) for c in known['corporations']])
    out['corporations'] = {}

    for corp in Corporation.objects.filter(pk__in=corps):
        out['corporations'][corp.pk] = {}
        out['corporations'][corp.pk]['id'] = corp.pk
        out['corporations'][corp.pk]['name'] = corp.name
        out['corporations'][corp.pk]['ticker'] = corp.ticker
        out['corporations'][corp.pk]['alliance'] = corp.alliance_id

        if corp.alliance_id and \
                (corp.alliance_id not in out['alliances'].keys()):
            out['alliances'][corp.alliance_id] = {}

    return out


def __alliances(request, out, known):
    alliances = set(out['alliances'].keys()) - \
        set([int(a) for a in known['alliances']])
    out['alliances'] = {}

    for alliance in Alliance.objects.filter(pk__in=alliances):
        out['alliances'][alliance.pk] = {}
        out['alliances'][alliance.pk]['id'] = alliance.pk
        out['alliances'][alliance.pk]['name'] = alliance.name
        out['alliances'][alliance.pk]['short_name'] = alliance.short_name

    return out


def __event_log(request, out, known):
    out['events'] = []
    for event in Event.objects.filter(user=request.user)[:10]:
        item = {}
        item['issued'] = event.issued
        item['text'] = event.text

        out['events'].append(item)

    return out


def __summary(request, out, known):
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


def __systems(request, out, known):
    if 'systems' in out.keys():
        system_names = set(out['systems'].keys()) - set(known['systems'])
        out['systems'] = {}

        systems = System.objects.all()
        systems = systems.select_related('constellation__region')
        systems = systems.filter(name__in=system_names)

        for system in systems:
            out['systems'][system.name] = {}
            out['systems'][system.name]['constellation'] = \
                system.constellation.name
            out['systems'][system.name]['region'] = \
                system.constellation.region.name

    return out


def __getRefreshTimes(out):
    key_to_character = {}

    keys = set()
    urls = [
        u'/account/AccountStatus.xml.aspx',
        u'/char/SkillQueue.xml.aspx',
        u'/char/CharacterSheet.xml.aspx'
    ]

    for charid, char in out['characters'].items():
        keys.add(char['apikey']['keyid'])

        if not char['apikey']['keyid'] in key_to_character:
            key_to_character[char['apikey']['keyid']] = []

        key_to_character[char['apikey']['keyid']].append(charid)

    out['refresh_hints'] = {
        'character': {},
        'skill_queue': {},
    }

    for task in TaskState.objects.filter(url__in=urls, keyid__in=list(keys)):
        if task.url == u'/account/AccountStatus.xml.aspx':
            for charid in key_to_character[task.keyid]:
                if charid in out['refresh_hints']['character']:
                    if out['refresh_hints']['character'][charid] > \
                            task.next_time:
                        out['refresh_hints']['character'][charid] = \
                            task.next_time
                else:
                    out['refresh_hints']['character'][charid] = task.next_time

        elif task.url == u'/char/SkillQueue.xml.aspx':
            out['refresh_hints']['skill_queue'][task.parameter] = \
                task.next_time
        elif task.url == u'/char/CharacterSheet.xml.aspx':
            if task.parameter in out['refresh_hints']['character']:
                if out['refresh_hints']['character'][task.parameter] > \
                        task.next_time:
                    out['refresh_hints']['character'][task.parameter] = \
                        task.next_time
            else:
                out['refresh_hints']['character'][task.parameter] = \
                    task.next_time

    return out

ALL_OPTIONS = OrderedDict([
    ('characters', __characters),
    ('skill_queues', __skill_queues),

    ('corporations', __corporations),
    ('alliances', __alliances),
    ('systems', __systems),

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
    out['systems'] = {}

    char_ids = request.REQUEST.getlist('characters')
    if char_ids:
        for id in char_ids:
            out['characters'][int(id)] = {}

    corp_ids = request.REQUEST.getlist('corporations')
    if corp_ids:
        for id in corp_ids:
            out['corporations'][int(id)] = {}

    alliance_ids = request.REQUEST.getlist('alliances')
    if alliance_ids:
        for id in alliance_ids:
            out['alliances'][int(id)] = {}

    system_names = request.REQUEST.getlist('systems')
    if system_names:
        for id in system_names:
            out['systems'][int(id)] = {}

    known = {
        'ships': [],
        'corporations': [],
        'alliances': [],
        'systems': [],
    }

    for key in known.keys():
        known[key] = request.REQUEST.getlist('known_' + key)

    tt.add_time('prep')

    # Because we want to get the next refresh time for the api calls
    # We need to ensure we have the apikey's
    if 'characters' not in request_options:
        if 'skill_queues' in request_options:
            request_options.append('characters')

    for opt in ALL_OPTIONS.keys():
        if opt in request_options:
            out = ALL_OPTIONS[opt](request, out, known)
            tt.add_time(opt)

    out = __getRefreshTimes(out)
    tt.add_time('refresh times')

    if settings.DEBUG:
        tt.finished()

    return HttpResponse(
        content=json.dumps(out, cls=DjangoJSONEncoder),
        content_type='application/json'
    )
