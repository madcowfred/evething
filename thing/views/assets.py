from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.http import HttpResponse

from thing.models import *
from thing.stuff import *

# ---------------------------------------------------------------------------
# Assets
@login_required
def assets(request):
    tt = TimerThing('assets')

    character_ids = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))
    characters = Character.objects.in_bulk(character_ids)
    
    corporation_ids = list(APIKey.objects.filter(user=request.user).exclude(corp_character=None).values_list('corp_character__corporation__id', flat=True))
    corporations = Corporation.objects.in_bulk(corporation_ids)

    # apply our initial set of filters
    assets = Asset.objects.filter(
        Q(character__in=character_ids, corporation_id__isnull=True)
        |
        Q(corporation_id__in=corporation_ids)
    )
    assets = assets.prefetch_related('item__item_group__category', 'inv_flag', 'system', 'station')
    #assets = assets.distinct()

    tt.add_time('init')

    # retrieve any supplied filter values
    f_types = request.GET.getlist('type')
    f_comps = request.GET.getlist('comp')
    f_values = request.GET.getlist('value')

    # run.
    filters = []
    if len(f_types) == len(f_comps) == len(f_values):
        # type, comparison, value
        for ft, fc, fv in zip(f_types, f_comps, f_values):
            # character
            if ft == 'char' and fv.isdigit():
                if fc == 'eq':
                    assets = assets.filter(character_id=fv, corporation_id__isnull=True)
                elif fc == 'ne':
                    assets = assets.exclude(character_id=fv, corporation_id__isnull=True)

                filters.append((ft, fc, int(fv)))

            # corporation
            elif ft == 'corp' and fv.isdigit():
                if fc == 'eq':
                    assets = assets.filter(corporation_id=fv)
                elif fc == 'ne':
                    assets = assets.exclude(corporation_id=fv)

                filters.append((ft, fc, int(fv)))

    # if no valid filters were found, add a dummy one
    if not filters:
        filters.append(('', '', ''))

    tt.add_time('filters')

    asset_map = {}
    for asset in assets:
        asset_map[asset.asset_id] = asset

    tt.add_time('asset map')

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
            if asset.character_id not in characters:
                continue

            # character and corporation
            asset.z_character = characters[asset.character_id]
            asset.z_corporation = corporations.get(asset.corporation_id)

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
            k = asset.system_or_station()

            # system/station asset
            #if k is not None:
            # base asset, always add
            if asset.parent == 0:
                asset.z_k = k
                asset.z_indent = 0

                if k not in systems:
                    loc_totals[k] = 0
                    systems[k] = []
                
                loc_totals[k] += asset.z_total
                systems[k].append(asset)

            # asset is inside something, assign it to parent
            else:
                parent = asset_lookup.get(asset.parent, None)
                if parent is None:
                    continue

                # add to parent contents
                parent.z_contents.append(asset)

                # set various things from parent
                asset.z_k = parent.z_k
                asset.z_indent = parent.z_indent + 1

                # add this to the parent entry in loc_totals
                loc_totals[asset.z_k] += asset.z_total
                parent.z_total += asset.z_total

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

    out = render_page(
        'thing/assets.html',
        {
            'characters': characters,
            'corporations': corporations,
            'filters': filters,
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
