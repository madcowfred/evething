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

import json
import operator

from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.http import HttpResponse

from thing.models import *
from thing.stuff import *

# ---------------------------------------------------------------------------

ASSETS_EXPECTED = {
    'char': {
        'label': 'Character',
        'comps': ['eq', 'ne', 'in'],
        'number': True,
    },
    'corp': {
        'label': 'Corporation',
        'comps': ['eq', 'ne', 'in'],
        'number': True,
    },
    'invflag': {
        'label': 'Inventory Flag',
        'comps': ['eq', 'ne', 'in'],
    },
    'item': {
        'label': 'Item',
        'comps': ['eq', 'ne', 'in'],
    },
    'itemcat': {
        'label': 'Item Category',
        'comps': ['eq', 'ne', 'in'],
    },
    'station': {
        'label': 'Station',
        'comps': ['eq', 'ne', 'in'],
    },
    'system': {
        'label': 'System',
        'comps': ['eq', 'ne', 'in'],
    },
}

# ---------------------------------------------------------------------------
# Assets summary
@login_required
def assets_summary(request):
    tt = TimerThing('assets_summary')

    characters = Character.objects.filter(apikeys__user=request.user.id).distinct()
    character_ids = []
    character_map = {}
    for character in characters:
        character_ids.append(character.id)
        character_map[character.id] = character

    corporations = Corporation.objects.filter(pk__in=APIKey.objects.filter(user=request.user).exclude(corp_character=None).values('corp_character__corporation'))
    corporation_ids = []
    corporation_map = {}
    for corporation in corporations:
        corporation_ids.append(corporation.id)
        corporation_map[corporation.id] = corporation

    tt.add_time('init')

    summary_qs = AssetSummary.objects.filter(
        Q(character__in=character_ids, corporation_id=0)
        |
        Q(corporation_id__in=corporation_ids)
    ).select_related(
        'character',
        'system',
        'station',
    )

    # Calculate totals and organise data
    overall_total = dict(items=0, value=0, volume=0)
    totals = {}
    total_data = {}
    summary_data = {}
    for summary in summary_qs:
        summary.z_corporation = corporation_map.get(summary.corporation_id)
        if summary.station:
            station_name = summary.station.name
        else:
            station_name = None

        # Overall totals
        overall_total['items'] += summary.total_items
        overall_total['value'] += summary.total_value
        overall_total['volume'] += summary.total_volume

        # Per system/station totals
        k = (summary.system.name, station_name, summary.system_id, summary.station_id)
        totals.setdefault(k, dict(items=0, value=0, volume=0))['items'] += summary.total_items
        totals[k]['value'] += summary.total_value
        totals[k]['volume'] += summary.total_volume

        # Per character/corporation totals
        k = summary.corporation_id or summary.character_id
        total_data.setdefault(k, dict(items=0, value=0, volume=0))['items'] += summary.total_items
        total_data[k]['value'] += summary.total_value
        total_data[k]['volume'] += summary.total_volume

        # Organise summary data
        if summary.z_corporation:
            k = (summary.z_corporation.name, summary.character.name, summary.corporation_id, summary.character_id)
        else:
            k = (None, summary.character.name, None, summary.character_id)
        summary_data.setdefault(k, []).append([summary.system.name, station_name, summary])

    tt.add_time('organise data')

    # Sort data!
    totals_list = sorted(totals.items())

    for k, v in summary_data.items():
        v.sort()

    summary_list = summary_data.items()
    summary_list.sort()

    tt.add_time('sort data')

    # Render template
    out = render_page(
        'thing/assets_summary.html',
        {
            'json_data': _json_data(characters, corporations, []),
            'characters': characters,
            'corporations': corporations,
            'overall_total': overall_total,
            'totals_list': totals_list,
            'total_data': total_data,
            'summary_list': summary_list,
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
# Assets filter
@login_required
def assets_filter(request):
    tt = TimerThing('assets')

    characters = Character.objects.filter(apikeys__user=request.user.id).distinct()
    character_ids = []
    character_map = {}
    for character in characters:
        character_ids.append(character.id)
        character_map[character.id] = character

    corporations = Corporation.objects.filter(pk__in=APIKey.objects.filter(user=request.user).exclude(corp_character=None).values('corp_character__corporation'))
    corporation_ids = []
    corporation_map = {}
    for corporation in corporations:
        corporation_ids.append(corporation.id)
        corporation_map[corporation.id] = corporation

    # apply our initial set of filters
    assets = Asset.objects.filter(
        Q(character__in=character_ids, corporation_id=0)
        |
        Q(corporation_id__in=corporation_ids)
    )
    assets = assets.prefetch_related('item__item_group__category', 'inv_flag', 'system', 'station')
    #assets = assets.distinct()

    tt.add_time('init')

    # Parse and apply filters
    filters = parse_filters(request, ASSETS_EXPECTED)

    if 'char' in filters:
        qs = []
        for fc, fv in filters['char']:
            if fc == 'eq':
                qs.append(Q(character=fv, corporation_id=0))
            elif fc == 'ne':
                qs.append(~Q(character=fv, corporation_id=0))
        assets = assets.filter(reduce(operator.ior, qs))

    if 'corp' in filters:
        qs = []
        for fc, fv in filters['corp']:
            if fc == 'eq':
                if fv == -1:
                    qs.append(Q(corporation_id__gt=0))
                else:
                    qs.append(Q(corporation_id=fv))
            elif fc == 'ne':
                if fv == -1:
                    qs.append(Q(corporation_id=0))
                else:
                    qs.append(~Q(corporation_id=fv))
        assets = assets.filter(reduce(operator.ior, qs))

    if 'invflag' in filters:
        qs = []
        for fc, fv in filters['invflag']:
            if fc == 'eq' and fv.isdigit():
                qs.append(Q(inv_flag_id=fv))
            elif fc == 'ne' and fv.isdigit():
                qs.append(~Q(inv_flag_id=fv))
            elif fc == 'in':
                qs.append(Q(inv_flag__name__icontains=fv))
        assets = assets.filter(reduce(operator.ior, qs))

    if 'item' in filters:
        qs = []
        for fc, fv in filters['item']:
            if fc == 'eq':
                qs.append(Q(item__name=fv))
            elif fc == 'ne':
                qs.append(~Q(item__name=fv))
            elif fc == 'in':
                qs.append(Q(item__name__icontains=fv))
        assets = assets.filter(reduce(operator.ior, qs))

    if 'itemcat' in filters:
        qs = []
        for fc, fv in filters['itemcat']:
            if fc == 'eq':
                if fv.isdigit():
                    qs.append(Q(item__item_group__category=fv))
                else:
                    qs.append(Q(item__item_group__category__name=fv))
            elif fc == 'ne':
                if fv.isdigit():
                    qs.append(~Q(item__item_group__category=fv))
                else:
                    qs.append(~Q(item__item_group__category__name=fv))
            elif fc == 'in':
                qs.append(Q(item__item_group__category__name__icontains=fv))
        assets = assets.filter(reduce(operator.ior, qs))

    if 'station' in filters:
        qs = []
        for fc, fv in filters['station']:
            if fc == 'eq':
                if fv.isdigit():
                    qs.append(Q(station=fv))
                else:
                    qs.append(Q(station__name=fv))
            elif fc == 'ne':
                if fv.isdigit():
                    qs.append(~Q(station=fv))
                else:
                    qs.append(~Q(station__name=fv))
            elif fc == 'in':
                qs.append(Q(station__name__icontains=fv))
        assets = assets.filter(reduce(operator.ior, qs))

    if 'system' in filters:
        qs = []
        for fc, fv in filters['system']:
            if fc == 'eq':
                if fv.isdigit():
                    qs.append(Q(system=fv))
                else:
                    qs.append(Q(system__name=fv))
            elif fc == 'ne':
                if fv.isdigit():
                    qs.append(~Q(system=fv))
                else:
                    qs.append(~Q(system__name=fv))
            elif fc == 'in':
                qs.append(Q(system__name__icontains=fv))
        assets = assets.filter(reduce(operator.ior, qs))

    tt.add_time('filters')

    asset_map = {}
    for asset in assets:
        asset_map[asset.asset_id] = asset

    tt.add_time('asset map')

    # do parent checks now, ugh
    recurse_you_fool = True
    recurse_assets = assets
    while recurse_you_fool:
        parents = set()
        for asset in recurse_assets:
            if asset.parent not in asset_map:
                parents.add(asset.parent)

        # found some orphan children, better go fetch some more assets
        if parents:
            recurse_assets = Asset.objects.filter(
                asset_id__in=parents,
            ).prefetch_related(
                'item__item_group__category',
                'inv_flag',
                'system',
                'station',
            )

            for asset in recurse_assets:
                asset.z_muted = True
                asset_map[asset.asset_id] = asset

        # No more orphans, escape
        else:
            recurse_you_fool = False

    # initialise data structures
    asset_lookup = {}
    loc_totals = {}
    systems = {}
    last_count = 999999999999999999

    while True:
        assets_now = asset_map.values()
        assets_len = len(assets_now)
        if assets_len == 0:
            break
        if assets_len == last_count:
            print 'infinite loop in assets?! %s' % (assets_len)
            break
        last_count = assets_len

        for asset in assets_now:
            # need to recurse this one later
            if asset.parent and asset_lookup.get(asset.parent) is None:
                continue

            asset.z_contents = []
            asset_lookup[asset.asset_id] = asset
            del asset_map[asset.asset_id]

            # skip missing character ids
            if asset.character_id not in character_map:
                continue

            # character and corporation
            asset.z_character = character_map.get(asset.character_id)
            asset.z_corporation = corporation_map.get(asset.corporation_id)

            # zz blueprints
            if asset.item.item_group.category.name == 'Blueprint':
                asset.z_blueprint = min(-1, asset.raw_quantity)
            else:
                asset.z_blueprint = 0

            # total value of this asset stack
            if asset.z_blueprint >= 0:
                # capital ships!
                if asset.item.item_group.name in ('Capital Industrial Ship', 'Carrier', 'Dreadnought', 'Supercarrier', 'Titan'):
                    asset.z_capital = True
                asset.z_price = asset.item.sell_price
            # BPOs use the base (NPC) price
            elif asset.z_blueprint == -1:
                asset.z_price = asset.item.base_price
            # BPCs count as 0 value for now
            else:
                asset.z_price = 0

            asset.z_total = asset.quantity * asset.z_price
            asset.z_volume = (asset.quantity * asset.item.volume).quantize(Decimal('0.01'))

            # work out if this is a system or station asset
            asset.z_k = asset.system_or_station()
            if asset.z_k not in systems:
                loc_totals[asset.z_k] = 0
                systems[asset.z_k] = []

            # base asset, always add
            if asset.parent == 0:
                asset.z_indent = 0

                loc_totals[asset.z_k] += asset.z_total
                systems[asset.z_k].append(asset)

            # asset is inside something, assign it to parent
            else:
                # parent doesn't exist yet
                parent = asset_lookup.get(asset.parent)
                if parent is None:
                    continue

                # add to parent contents
                parent.z_contents.append(asset)

                # add this to the parent entry in loc_totals
                loc_totals[asset.z_k] += asset.z_total

                # add the total value to every parent of this asset
                p = parent
                while p is not None:
                    p.z_total += asset.z_total
                    p = asset_lookup.get(p.parent)

                # guess at what indent level this should be
                asset.z_indent = getattr(parent, 'z_indent', 0) + 1

                # Celestials (containers) need some special casing
                if parent.item.item_group.category.name == 'Celestial':
                    asset.z_locked = (asset.inv_flag.name == 'Locked')

                    asset.z_type = asset.item.item_group.category.name

                else:
                    # inventory group
                    asset.z_slot = asset.inv_flag.nice_name()
                    # corporation hangar
                    if asset.z_corporation is not None and asset.z_slot.startswith('CorpSAG'):
                        asset.z_slot = getattr(asset.z_corporation, 'division%s' % (asset.z_slot[-1]))

    tt.add_time('main loop')

    # get a total asset value
    total_value = sum(loc_totals.values())

    # decorate/sort/undecorate for our strange sort requirements :(
    for system_name in systems:
        temp = [(asset.z_character.name.lower(), len(asset.z_contents) == 0, asset.item.name, asset.name, asset) for asset in systems[system_name]]
        temp.sort()
        systems[system_name] = [s[-1] for s in temp]

    sorted_systems = sorted(systems.items())

    tt.add_time('sort root')

    # recursively sort asset.z_contents
    for asset_set in systems.values():
        for asset in asset_set:
            _content_sort(asset)

    tt.add_time('sort contents')

    # Render template
    out = render_page(
        'thing/assets_filter.html',
        {
            'json_data': _json_data(characters, corporations, filters),
            'characters': characters,
            'corporations': corporations,
            'total_value': total_value,
            'systems': sorted_systems,
            'loc_totals': loc_totals,
        },
        request,
        character_ids,
        corporation_ids,
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

# Recursively sort the contents of an asset
def _content_sort(asset):
    if asset.z_contents:
        # decorate/sort/undecorate argh
        temp = [(c.inv_flag.sort_order(), c.item.name, c) for c in asset.z_contents]
        temp.sort()
        asset.z_contents = [s[2] for s in temp]
        for asset in asset.z_contents:
            _content_sort(asset)

# ---------------------------------------------------------------------------

def _json_data(characters, corporations, filters):
    data = dict(
        expected=ASSETS_EXPECTED,
        filters=filters,
        values=dict(
            char={},
            corp={},
            invflag={},
            itemcat={},
        ),
    )

    for char in characters:
        data['values']['char'][char.id] = char.name.replace("'", '&apos;')
    for corp in corporations:
        data['values']['corp'][corp.id] = corp.name.replace("'", '&apos;')
    for invflag in InventoryFlag.objects.all():
        data['values']['invflag'][invflag.id] = invflag.name
    for itemcat in ItemCategory.objects.all():
        data['values']['itemcat'][itemcat.id] = itemcat.name

    return json.dumps(data)
