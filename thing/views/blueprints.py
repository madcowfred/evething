import csv

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.shortcuts import redirect, get_object_or_404

from thing import queries
from thing.models import *
from thing.stuff import *

# ---------------------------------------------------------------------------

ONE_DAY = 24 * 60 * 60

# ---------------------------------------------------------------------------
# List of blueprints we own
@login_required
def blueprints(request):
    tt = TimerThing('blueprints')

    # Get a valid number of runs
    try:
        runs = int(request.GET.get('runs', '1'))
    except ValueError:
        runs = 1

    # Build a map of Blueprint.id -> BlueprintComponent
    bpc_map = {}
    bp_ids = BlueprintInstance.objects.filter(user=request.user.id).values_list('blueprint_id', flat=True)
    for bpc in BlueprintComponent.objects.select_related(depth=1).filter(blueprint__in=bp_ids):
        bpc_map.setdefault(bpc.blueprint.id, []).append(bpc)

    tt.add_time('bp->bpc map')

    # Assemble blueprint data
    bpis = []
    for bpi in BlueprintInstance.objects.select_related().filter(user=request.user.id):
        # Cache component list so we don't have to retrieve it multiple times
        components = bpi._get_components(components=bpc_map[bpi.blueprint.id], runs=runs)

        # Calculate a bunch of things we can't easily do via SQL
        bpi.z_count = bpi.blueprint.item.portion_size * runs
        bpi.z_production_time = bpi.calc_production_time(runs=runs)
        bpi.z_unit_cost_buy = bpi.calc_production_cost(components=components, runs=runs)
        bpi.z_unit_profit_buy = bpi.blueprint.item.sell_price - bpi.z_unit_cost_buy
        bpi.z_unit_cost_sell = bpi.calc_production_cost(runs=runs, use_sell=True, components=components)
        bpi.z_unit_profit_sell = bpi.blueprint.item.sell_price - bpi.z_unit_cost_sell

        bpis.append(bpi)

    tt.add_time('bp data')

    # Render template
    out = render_page(
        'thing/blueprints.html',
        {
            'blueprints': Blueprint.objects.all(),
            'bpis': bpis,
            'runs': runs,
        },
        request,
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

# Add a new blueprint
@login_required
def blueprints_add(request):
    bpi = BlueprintInstance(
        user=request.user,
        blueprint_id=request.GET['blueprint_id'],
        original=request.GET.get('original', False),
        material_level=request.GET['material_level'],
        productivity_level=request.GET['productivity_level'],
    )
    bpi.save()

    return redirect('blueprints')

@login_required
def blueprints_del(request):
    bpi = get_object_or_404(BlueprintInstance, user=request.user, pk=request.GET['bpi_id'])
    bpi.delete()

    return redirect('blueprints')

@login_required
def blueprints_edit(request):
    bpi = get_object_or_404(BlueprintInstance, user=request.user, pk=request.GET['bpi_id'])
    bpi.material_level = request.GET['new_ml']
    bpi.productivity_level = request.GET['new_pl']
    bpi.save()

    return redirect('blueprints')

# ---------------------------------------------------------------------------
# Export blueprints as CSV
@login_required
def blueprints_export(request):
    return render_page(
        'thing/blueprints_export.html',
        {
            'bpis': BlueprintInstance.objects.select_related().filter(user=request.user.id),
        },
        request,
    )

# Import blueprints from CSV
@login_required
def blueprints_import(request):
    csvdata = ''

    if request.method == 'POST':
        if 'csv' in request.POST:
            csvdata = request.POST['csv']

            # parse CSV data
            data = []
            for row in csv.reader(csvdata.splitlines()):
                if len(row) != 4:
                    continue
                if row[1] not in ('0', '1'):
                    continue
                if not (row[2].isdigit() or (row[2][0] == '-' and row[2][1:].isdigit())):
                    continue
                if not (row[3].isdigit() or (row[3][0] == '-' and row[3][1:].isdigit())):
                    continue

                data.append(row)

            # retrieve blueprint data
            bpnames = set([d[0] for d in data])
            bp_map = {}
            for bp in Blueprint.objects.filter(name__in=bpnames):
                bp_map[bp.name] = bp

            # build new objects
            new = []
            for bpname, original, me, pe in data:
                bp = bp_map.get(bpname)
                if not bp:
                    continue

                new.append(BlueprintInstance(
                    user=request.user,
                    blueprint=bp,
                    original=original,
                    material_level=me,
                    productivity_level=pe,
                ))

            # actually create new objects if we have to
            if new:
                BlueprintInstance.objects.bulk_create(new)

                message = 'Successfully added %s new blueprints!' % (len(new))
                message_type = 'success'
            else:
                message = 'Invalid CSV data!'
                message_type = 'error'

        else:
            message = 'Invalid CSV data!'
            message_type = 'error'

    else:
        message = None
        message_type = None

    return render_page(
        'thing/blueprints_import.html',
        {
            'message': message,
            'message_type': message_type,
            'csv': csvdata,
        },
        request,
    )

# ---------------------------------------------------------------------------
# Calculate blueprint production details for X number of days
@login_required
def bpcalc(request):
    # Get a valid number of days
    try:
        days = max(1, int(request.GET.get('days', '7')))
    except ValueError:
        days = 7

    # Initialise variabls
    bpis = []
    bpi_totals = {
        'input_m3': Decimal('0.0'),
        'output_m3': Decimal('0.0'),
        'total_sell': Decimal('0.0'),
        'buy_build': Decimal('0.0'),
        'buy_profit': Decimal('0.0'),
        'buy_profit_per': Decimal('0.0'),
        'sell_build': Decimal('0.0'),
        'sell_profit': Decimal('0.0'),
        'sell_profit_per': Decimal('0.0'),
    }
    component_list = []
    comp_totals = {
        'volume': 0,
        'buy_total': 0,
        'sell_total': 0,
    }

    # Get the list of BPIs from GET vars
    bpi_list = map(int, request.GET.getlist('bpi'))
    if bpi_list:
        # Build a map of Blueprint.id -> BlueprintComponents
        bpc_map = {}
        bp_ids = BlueprintInstance.objects.filter(user=request.user.id, pk__in=bpi_list).values_list('blueprint_id', flat=True)
        for bpc in BlueprintComponent.objects.select_related(depth=1).filter(blueprint__in=bp_ids):
            bpc_map.setdefault(bpc.blueprint.id, []).append(bpc)

        # Do weekly movement in bulk
        item_ids = list(BlueprintInstance.objects.filter(user=request.user.id, pk__in=bpi_list).values_list('blueprint__item_id', flat=True))
        one_month_ago = datetime.datetime.utcnow() - datetime.timedelta(30)

        if item_ids:
            query = queries.bpcalc_movement % (', '.join(map(str, item_ids)))

            cursor = connection.cursor()
            cursor.execute(query, (days, one_month_ago,))
            move_map = {}
            for row in cursor:
                move_map[row[0]] = row[1]

            comps = {}
            # Fetch BlueprintInstance objects
            for bpi in BlueprintInstance.objects.select_related('blueprint__item').filter(user=request.user.id, pk__in=bpi_list):
                # Skip BPIs with no current price information
                if bpi.blueprint.item.sell_price == 0 and bpi.blueprint.item.buy_price == 0:
                    continue

                # Work out how many runs fit into the number of days provided
                pt = bpi.calc_production_time()
                runs = int((ONE_DAY * days) / pt)

                # Skip really long production items
                if runs == 0:
                    continue

                built = runs * bpi.blueprint.item.portion_size

                # Magical m3 stuff
                bpi.z_input_m3 = 0
                bpi.z_output_m3 = bpi.blueprint.item.volume * built

                # Add the components
                components = bpi._get_components(components=bpc_map[bpi.blueprint.id], runs=runs)
                for item, amt in components:
                    comps[item] = comps.get(item, 0) + amt
                    bpi.z_input_m3 += (item.volume * amt)

                # Calculate a bunch of things we can't easily do via SQL
                bpi.z_total_time = pt * runs
                bpi.z_runs = runs
                bpi.z_built = built
                bpi.z_total_sell = bpi.blueprint.item.sell_price * built
                bpi.z_buy_build = bpi.calc_production_cost(runs=runs, components=components) * built
                bpi.z_sell_build = bpi.calc_production_cost(runs=runs, use_sell=True, components=components) * built

                bpi.z_buy_profit = bpi.z_total_sell - bpi.z_buy_build
                bpi.z_buy_profit_per = (bpi.z_buy_profit / bpi.z_buy_build * 100).quantize(Decimal('.1'))
                bpi.z_sell_profit = bpi.z_total_sell - bpi.z_sell_build
                bpi.z_sell_profit_per = (bpi.z_sell_profit / bpi.z_sell_build * 100).quantize(Decimal('.1'))

                #bpi.z_volume_week = bpi.blueprint.item.get_volume()
                bpi.z_volume_week = move_map.get(bpi.blueprint.item.id, 0)
                if bpi.z_volume_week:
                    bpi.z_volume_percent = (bpi.z_built / bpi.z_volume_week * 100).quantize(Decimal('.1'))

                # Update totals
                bpi_totals['input_m3'] += bpi.z_input_m3
                bpi_totals['output_m3'] += bpi.z_output_m3
                bpi_totals['total_sell'] += bpi.z_total_sell
                bpi_totals['buy_build'] += bpi.z_buy_build
                bpi_totals['buy_profit'] += bpi.z_buy_profit
                bpi_totals['sell_build'] += bpi.z_sell_build
                bpi_totals['sell_profit'] += bpi.z_sell_profit

                bpis.append(bpi)

            # Components
            for item, amt in comps.items():
                component_list.append({
                    'item': item,
                    'amount': amt,
                    'volume': (amt * item.volume).quantize(Decimal('.1')),
                    'buy_total': amt * item.buy_price,
                    'sell_total': amt * item.sell_price,
                })
            component_list.sort(key=lambda c: c['item'].name)

            # Do some sums
            if bpi_totals['buy_profit'] and bpi_totals['buy_build']:
                bpi_totals['buy_profit_per'] = (bpi_totals['buy_profit'] / bpi_totals['buy_build'] * 100).quantize(Decimal('.1'))

            if bpi_totals['sell_profit'] and bpi_totals['sell_build']:
                bpi_totals['sell_profit_per'] = (bpi_totals['sell_profit'] / bpi_totals['sell_build'] * 100).quantize(Decimal('.1'))

            comp_totals['volume'] = sum(comp['volume'] for comp in component_list)
            comp_totals['buy_total'] = sum(comp['buy_total'] for comp in component_list)
            comp_totals['sell_total'] = sum(comp['sell_total'] for comp in component_list)

    # Render template
    return render_page(
        'thing/bpcalc.html',
        {
            'bpis': bpis,
            'bpi_totals': bpi_totals,
            'components': component_list,
            'comp_totals': comp_totals,
            'days': days,
        },
        request,
    )

# ---------------------------------------------------------------------------
