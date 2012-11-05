from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.template import RequestContext

from coffin.shortcuts import *

from thing.models import *
from thing.stuff import TimerThing

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
    #assets = Asset.objects.select_related('system', 'station', 'inv_flag')
    assets = Asset.objects.filter(
        Q(character__in=character_ids)
        &
        (
            Q(corporation_id__isnull=True)
            |
            Q(corporation_id__in=corporation_ids)
        )
    )
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

    # gather data for bulk fetching
    inv_flag_ids = set()
    item_ids = set()
    station_ids = set()
    system_ids = set()

    for asset in assets:
        inv_flag_ids.add(asset.inv_flag_id)
        item_ids.add(asset.item_id)
        if asset.station_id is not None:
            station_ids.add(asset.station_id)
        if asset.system_id is not None:
            system_ids.add(asset.system_id)

    tt.add_time('assets prep')

    inv_flag_map = InventoryFlag.objects.in_bulk(inv_flag_ids)
    tt.add_time('bulk invflag')
    item_map = Item.objects.select_related().in_bulk(item_ids)
    tt.add_time('bulk item')
    station_map = Station.objects.in_bulk(station_ids)
    tt.add_time('bulk station')
    system_map = System.objects.in_bulk(system_ids)
    tt.add_time('bulk system')

    # initialise data structures
    ca_lookup = {}
    loc_totals = {}
    systems = {}

    for ca in assets:
        # skip missing character ids
        if ca.character_id not in characters:
            continue

        ca.z_inv_flag = inv_flag_map[ca.inv_flag_id]
        ca.z_item = item_map[ca.item_id]

        # character and corporation
        ca.z_character = characters[ca.character_id]
        ca.z_corporation = corporations.get(ca.corporation_id)

        # work out if this is a system or station asset
        k = getattr(station_map.get(ca.station_id, system_map.get(ca.system_id)), 'name', None)

        # zz blueprints
        if ca.z_item.item_group.category.name == 'Blueprint':
            ca.z_blueprint = min(-1, ca.raw_quantity)
        else:
            ca.z_blueprint = 0
        
        # total value of this asset stack
        if ca.z_blueprint >= 0:
            # capital ship, calculate build cost
            if ca.z_item.item_group.name in ('Carrier', 'Dreadnought', 'Supercarrier', 'Titan'):
                ca.z_capital = True
            ca.z_price = ca.z_item.sell_price
        # BPOs use the base price
        elif ca.z_blueprint == -1:
            ca.z_price = ca.z_item.base_price
        # BPCs count as 0 value
        else:
            ca.z_price = 0
        
        ca.z_total = ca.quantity * ca.z_price

        # system/station asset
        if k is not None:
            ca_lookup[ca.id] = ca

            ca.z_k = k
            ca.z_contents = []

            if k not in systems:
                loc_totals[k] = 0
                systems[k] = []
            
            loc_totals[k] += ca.z_total
            systems[k].append(ca)

        # asset is inside something, assign it to parent
        else:
            parent = ca_lookup.get(ca.parent_id, None)
            if parent is None:
                continue

            # add to parent's contents
            parent.z_contents.append(ca)

            # add this to the parent's entry in loc_totals
            loc_totals[parent.z_k] += ca.z_total
            parent.z_total += ca.z_total

            # Celestials (containers) need some special casing
            if parent.z_item.item_group.category.name == 'Celestial':
                ca.z_locked = (ca.z_inv_flag.name == 'Locked')

                ca.z_group = ca.z_item.item_group.category.name

            else:
                # inventory group
                ca.z_group = ca.z_inv_flag.nice_name()
                # corporation hangar
                if ca.z_corporation is not None and ca.z_group.startswith('CorpSAG'):
                    ca.z_group = getattr(ca.z_corporation, 'division%s' % (ca.z_group[-1]))

    tt.add_time('main loop')

    # add contents to the parent total
    for cas in systems.values():
        for ca in cas:
            if hasattr(ca, 'z_contents'):
                #for content in ca.z_contents:
                #    ca.z_total += content.z_total

                # decorate/sort/undecorate argh
                temp = [(c.z_inv_flag.sort_order(), c.z_item.name, c) for c in ca.z_contents]
                temp.sort()
                ca.z_contents = [s[2] for s in temp]

                ca.z_mod = len(ca.z_contents) % 2

    tt.add_time('parents')

    # get a total asset value
    total_value = sum(loc_totals.values())

    # decorate/sort/undecorate for our strange sort requirements :(
    for system_name in systems:
        temp = [(ca.z_character.name.lower(), ca.is_leaf_node(), ca.z_item.name, ca.name, ca) for ca in systems[system_name]]
        temp.sort()
        systems[system_name] = [s[-1] for s in temp]

    sorted_systems = sorted(systems.items())

    tt.add_time('sort')

    out = render_to_response(
        'thing/assets.html',
        {
            'characters': characters,
            'corporations': corporations,
            'filters': filters,
            'total_value': total_value,
            'systems': sorted_systems,
            'loc_totals': loc_totals,
        },
        context_instance=RequestContext(request)
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

# ---------------------------------------------------------------------------
