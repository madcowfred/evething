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
from django.db.models import Q, Sum

from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8
from thing.templatetags.thing_extras import commas, shortduration

ONE_DAY = 24 * 60 * 60
EXPIRE_WARNING = 10 * ONE_DAY


@login_required
def home(request):
    """Home page"""
    tt = TimerThing('home')

    profile = request.user.profile

    tt.add_time('profile')

    # Make a set of characters to hide
    hide_characters = set(int(c) for c in profile.home_hide_characters.split(',') if c)

    # Initialise various data structures
    now = datetime.datetime.utcnow()
    total_balance = 0

    api_keys = set()
    training = set()
    chars = {}
    ship_item_ids = set()

    # Try retrieving characters from cache
    cache_key = 'home:characters:%d' % (request.user.id)
    characters = cache.get(cache_key)
    # Not cached, fetch from database and cache
    if characters is None:
        character_qs = Character.objects.filter(
            apikeys__user=request.user,
            apikeys__valid=True,
            apikeys__key_type__in=(APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE),
        ).prefetch_related(
            'apikeys',
        ).select_related(
            'config',
            'details',
        ).distinct()

        # Django 1.5 workaround for the stupid change from a non-existent reverse
        # relation returning None to it raising self.related.model.DoesNotExist :(
        characters = []
        char_map = {}
        for c in character_qs:
            try:
                c.details is not None
            except:
                pass
            else:
                characters.append(c)
                char_map[c.id] = c

        tt.add_time('c1')

        # Fetch skill data now WITHOUT Unpublished SP
        cskill_qs = CharacterSkill.objects.filter(
            character__in=char_map.keys(),
            skill__item__market_group__isnull=False,
        ).values(
            'character',
        ).annotate(
            total_sp=Sum('points'),
        )
        for cskill in cskill_qs:
            char_map[cskill['character']].total_sp = cskill['total_sp']

        cache.set(cache_key, characters, 300)

        tt.add_time('c2')

    for character in characters:
        char_keys = [ak for ak in character.apikeys.all() if ak.user_id == request.user.id]
        api_keys.update(char_keys)

        chars[character.id] = character
        character.z_apikey = char_keys[0]
        character.z_training = {}

        total_balance += character.details.wallet_balance
        if character.details.ship_item_id is not None:
            ship_item_ids.add(character.details.ship_item_id)

    tt.add_time('characters')

    # Retrieve ship information
    ship_map = Item.objects.in_bulk(ship_item_ids)
    tt.add_time('ship_items')

    # Do skill training check - this can't be in the model because it
    # scales like crap doing individual queries
    skill_qs = []

    queues = SkillQueue.objects.filter(character__in=chars, end_time__gte=now)
    queues = queues.select_related('skill__item')
    for sq in queues:
        char = chars[sq.character_id]
        duration = total_seconds(sq.end_time - now)

        if 'sq' not in char.z_training:
            char.z_training['sq'] = sq
            char.z_training['skill_duration'] = duration
            char.z_training['sp_per_hour'] = int(sq.skill.get_sp_per_minute(char) * 60)
            char.z_training['complete_per'] = sq.get_complete_percentage(now, char)
            training.add(char.z_apikey)

            skill_qs.append(Q(character=char, skill=sq.skill))

        char.z_training['queue_duration'] = duration

    tt.add_time('training')

    # Retrieve training skill information
    if skill_qs:
        for cs in CharacterSkill.objects.filter(reduce(operator.ior, skill_qs)):
            chars[cs.character_id].z_tskill = cs

    tt.add_time('training skills')

    # Do total skill point aggregation
    total_sp = 0
    for char in characters:
        char.z_total_sp = getattr(char, 'total_sp', 0)
        if 'sq' in char.z_training and hasattr(char, 'z_tskill'):
            char.z_total_sp += int(char.z_training['sq'].get_completed_sp(char.z_tskill, now, char))

        total_sp += char.z_total_sp

    tt.add_time('total_sp')

    # Try retrieving total asset value from cache
    cache_key = 'home:total_assets:%d' % (request.user.id)
    total_assets = cache.get(cache_key)
    # Not cached, fetch from database and cache
    if total_assets is None:
        total_assets = AssetSummary.objects.filter(
            character__in=chars.keys(),
            corporation_id=0,
        ).aggregate(
            t=Sum('total_value'),
        )['t']
        cache.set(cache_key, total_assets, 300)

    tt.add_time('total_assets')

    # Work out who is and isn't training
    not_training = api_keys - training

    # Do notifications
    for char_id, char in chars.items():
        char.z_notifications = []

        # Game time warnings
        if char.z_apikey.paid_until:
            timediff = total_seconds(char.z_apikey.paid_until - now)

            if timediff < 0:
                char.z_notifications.append({
                    'icon': 'clock-o',
                    'text': 'Expired',
                    'tooltip': 'Game time has expired!',
                    'span_class': 'low-game-time',
                })

            elif timediff < EXPIRE_WARNING:
                char.z_notifications.append({
                    'icon': 'clock-o',
                    'text': shortduration(timediff),
                    'tooltip': 'Remaining game time is low!',
                    'span_class': 'low-game-time',
                })

        # API key warnings
        if char.z_apikey.expires:
            timediff = total_seconds(char.z_apikey.expires - now)
            if timediff < EXPIRE_WARNING:
                char.z_notifications.append({
                    'icon': 'key',
                    'text': shortduration(timediff),
                    'tooltip': 'API key is close to expiring!',
                })

        # Empty skill queue
        if char.z_apikey in not_training:
            char.z_notifications.append({
                'icon': 'list-ol',
                'text': 'Empty!',
                'tooltip': 'Skill queue is empty!',
            })

        if char.z_training:
            # Room in skill queue
            if char.z_training['queue_duration'] < ONE_DAY:
                timediff = ONE_DAY - char.z_training['queue_duration']
                char.z_notifications.append({
                    'icon': 'list-ol',
                    'text': shortduration(timediff),
                    'tooltip': 'Skill queue is not full!',
                })

            # Missing implants
            skill = char.z_training['sq'].skill
            pri_attrs = Skill.ATTRIBUTE_MAP[skill.primary_attribute]
            sec_attrs = Skill.ATTRIBUTE_MAP[skill.secondary_attribute]
            pri_bonus = getattr(char.details, pri_attrs[1])
            sec_bonus = getattr(char.details, sec_attrs[1])

            t = []
            if pri_bonus == 0:
                t.append(skill.get_primary_attribute_display())
            if sec_bonus == 0:
                t.append(skill.get_secondary_attribute_display())

            if t:
                char.z_notifications.append({
                    'icon': 'lightbulb-o',
                    'text': ', '.join(t),
                    'tooltip': 'Missing stat implants for currently training skill!',
                })

        # Sort out well classes here ugh
        classes = []
        if char.z_apikey in not_training:
            if profile.home_highlight_backgrounds:
                classes.append('background-error')
            if profile.home_highlight_borders:
                classes.append('border-error')
        elif char.z_notifications:
            if profile.home_highlight_backgrounds:
                classes.append('background-warn')
            if profile.home_highlight_borders:
                classes.append('border-warn')
        else:
            if profile.home_highlight_backgrounds:
                classes.append('background-success')
            if profile.home_highlight_borders:
                classes.append('border-success')

        if classes:
            char.z_well_class = ' %s' % (' '.join(classes))
        else:
            char.z_well_class = ''

    tt.add_time('notifications')

    # Decorate/sort based on settings, ugh
    char_list = chars.values()
    if profile.home_sort_order == 'apiname':
        temp = [(c.z_apikey.group_name or 'ZZZ', c.z_apikey.name, c.name.lower(), c) for c in char_list]
    elif profile.home_sort_order == 'charname':
        temp = [(c.z_apikey.group_name or 'ZZZ', c.name.lower(), c) for c in char_list]
    elif profile.home_sort_order == 'corpname':
        temp = [(c.z_apikey.group_name or 'ZZZ', c.corporation.name.lower(), c.name.lower(), c) for c in char_list]
    elif profile.home_sort_order == 'totalsp':
        temp = [(c.z_apikey.group_name or 'ZZZ', getattr(c, 'z_total_sp', 0), c) for c in char_list]
    elif profile.home_sort_order == 'wallet':
        temp = [(c.z_apikey.group_name or 'ZZZ', c.details and c.details.wallet_balance, c.name.lower(), c) for c in char_list]

    temp.sort()
    if profile.home_sort_descending:
        temp.reverse()

    tt.add_time('sort')

    # Now group based on group_name
    bleh = OrderedDict()
    for temp_data in temp:
        bleh.setdefault(temp_data[0], []).append(temp_data[-1])

    char_lists = []
    for char_list in bleh.values():
        first = [char for char in char_list if char.z_training and char.id not in hide_characters]
        last = [char for char in char_list if not char.z_training and char.id not in hide_characters]
        char_lists.append(first + last)

    tt.add_time('group')

    # Try retrieving corporations from cache
    cache_key = 'home:corporations:%d' % (request.user.id)
    corporations = cache.get(cache_key)
    # Not cached, fetch from database and cache
    if corporations is None:
        corp_ids = Corporation.get_ids_with_access(request.user, APIKey.CORP_ACCOUNT_BALANCE_MASK)
        corp_map = OrderedDict()
        # WARNING: Theoritically we are exposing the wallet divison name which may not be exposed
        # if you only have the BALANCE_MASK or some shit
        for corp_wallet in CorpWallet.objects.select_related().filter(corporation__in=corp_ids):
            if corp_wallet.corporation_id not in corp_map:
                corp_map[corp_wallet.corporation_id] = corp_wallet.corporation
                corp_map[corp_wallet.corporation_id].wallets = []

            corp_map[corp_wallet.corporation_id].wallets.append(corp_wallet)

        corporations = corp_map.values()
        cache.set(cache_key, corporations, 300)

    tt.add_time('corps')

    # Try retrieving total corp asset value from cache
    cache_key = 'home:corp_assets:%d' % (request.user.id)
    corp_assets = cache.get(cache_key)
    # Not cached, fetch from database and cache
    if corp_assets is None:
        corp_ids = Corporation.get_ids_with_access(request.user, APIKey.CORP_ASSET_LIST_MASK)

        corp_assets = AssetSummary.objects.filter(
            corporation_id__in=corp_ids,
        ).aggregate(
            t=Sum('total_value'),
        )['t']
        cache.set(cache_key, corp_assets, 300)

    tt.add_time('corp_assets')

    # Render template
    out = render_page(
        'thing/home.html',
        {
            'profile': profile,
            'not_training': not_training,
            'total_balance': total_balance,
            'total_sp': total_sp,
            'total_assets': total_assets,
            'corp_assets': corp_assets,
            'corporations': corporations,
            #'characters': first + last,
            'characters': char_lists,
            'events': list(Event.objects.filter(user=request.user)[:10]),
            'ship_map': ship_map,
            #'task_count': task_count,
        },
        request,
        chars.keys(),
        [c.id for c in corporations]
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out
