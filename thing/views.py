import calendar
import datetime
from collections import OrderedDict
#import time

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.db import connection
from django.db.models import Avg, Count, Max, Min, Sum
from django.http import Http404
from django.shortcuts import *
from django.template import RequestContext

from evething.thing.models import *
from evething.thing import queries

# ---------------------------------------------------------------------------
# How many days to start warning about expiring accounts
EXPIRE_WARNING = datetime.timedelta(10)

# ---------------------------------------------------------------------------
# Home page
@login_required
def home(request):
    total_balance = 0

    now = datetime.datetime.utcnow()

    # Grab the initial set of characters and do some stuff
    apikeys = set()
    training = set()
    chars = OrderedDict()
    for char in Character.objects.select_related('apikey').filter(apikey__user=request.user).order_by('apikey__name', 'name'):
        char.z_training = {}
        chars[char.eve_character_id] = char
        apikeys.add(char.apikey_id)
        total_balance += char.wallet_balance

        # See if the account expires soon
        timediff = char.apikey.paid_until - now
        if timediff < EXPIRE_WARNING:
            char.z_expires = timediff.total_seconds()

    # Do skill training check - this can't be in the model because it
    # scales like crap doing individual queries
    utcnow = datetime.datetime.utcnow()
    queues = SkillQueue.objects.select_related().filter(character__in=chars.keys(), end_time__gte=utcnow)
    for sq in queues:
        char = chars[sq.character_id]
        if 'sq' not in char.z_training:
            char.z_training['sq'] = sq
            char.z_training['skill_duration'] = (sq.end_time - utcnow).total_seconds()
            char.z_training['sp_per_hour'] = int(sq.skill.get_sp_per_minute(char) * 60)
            char.z_training['complete_per'] = sq.get_complete_percentage(now)
            training.add(char.apikey_id)
        
        char.z_training['queue_duration'] = (sq.end_time - utcnow).total_seconds()
    
    # Do total skill point aggregation
    for cs in CharacterSkill.objects.select_related().filter(character__apikey__user=request.user).values('character').annotate(total_sp=Sum('points')):
        chars[cs['character']].z_total_sp = cs['total_sp']

    # Make separate lists of training and not training characters
    first = [char for char in chars.values() if char.z_training]
    last = [char for char in chars.values() if not char.z_training]
    
    # Get corporations this user has APIKeys for
    corp_ids = APIKey.objects.select_related().filter(user=request.user.id).exclude(corp_character=None).values_list('corp_character__corporation', flat=True)
    corporations = Corporation.objects.filter(pk__in=corp_ids)

    return render_to_response(
        'thing/home.html',
        {
            'not_training': apikeys - training,
            'total_balance': total_balance,
            'corporations': corporations,
            'characters': first + last,
            'sanitise': request.GET.get('sanitise', False)
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# List of blueprints we own
@login_required
def blueprints(request):
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
    
    # Render template
    return render_to_response(
        'thing/blueprints.html',
        {
            'blueprints': Blueprint.objects.all(),
            'bpis': bpis,
            'runs': runs,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Add a new blueprint
@login_required
def blueprints_add(request):
    bpi = BlueprintInstance(
        user=request.user,
        blueprint_id=request.GET['blueprint_id'],
        original=request.GET['original'],
        material_level=request.GET['material_level'],
        productivity_level=request.GET['productivity_level'],
    )
    bpi.save()
    
    return redirect('blueprints')

# ---------------------------------------------------------------------------
# Calculate blueprint production details for X number of days
DAY = 24 * 60 * 60
@login_required
def bpcalc(request):
    # Get a valid number of days
    try:
        days = int(request.GET.get('days', '7'))
    except ValueError:
        days = 7
    
    # Initialise variabls
    bpis = []
    bpi_totals = {
        'total_sell': Decimal('0.0'),
        'buy_build': Decimal('0.0'),
        'buy_profit': Decimal('0.0'),
        'sell_build': Decimal('0.0'),
        'sell_profit': Decimal('0.0'),
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
        
        query = """
SELECT  item_id, CAST(SUM(movement) / 30 * 7 AS decimal(18,2))
FROM    thing_pricehistory
WHERE   item_id IN (%s)
        AND date >= %%s
GROUP BY item_id
        """ % (', '.join(map(str, item_ids)))
        
        cursor = connection.cursor()
        cursor.execute(query, (one_month_ago,))
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
            runs = int((DAY * days) / pt)
            
            # Skip really long production items
            if runs == 0:
                continue
            
            built = runs * bpi.blueprint.item.portion_size
            
            # Add the components
            components = bpi._get_components(components=bpc_map[bpi.blueprint.id], runs=runs)
            for item, amt in components:
                comps[item] = comps.get(item, 0) + amt
            
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
    return render_to_response(
        'thing/bpcalc.html',
        {
            'bpis': bpis,
            'bpi_totals': bpi_totals,
            'components': component_list,
            'comp_totals': comp_totals,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------

def character(request, character_name):
    char = get_object_or_404(Character, name=character_name)

    # Check access
    public = True
    if request.user.is_authenticated() and request.user.id == char.apikey.user.id:
        public = False

    # If it's for public access, make sure this character is visible
    if public:
        try:
            config = char.config
        except CharacterConfig.DoesNotExist:
            raise Http404

        if not config.is_public:
            raise Http404
    else:
        config = {}
        for thing in ('show_clone', 'show_implants', 'show_skill_queue', 'show_wallet'):
            config[thing] = True

    # Retrieve the list of skills and group them by market group
    skills = OrderedDict()
    skill_totals = {}
    cur = None
    for cs in CharacterSkill.objects.select_related('skill__item__market_group', 'character').filter(character=char).order_by('skill__item__market_group__name', 'skill__item__name'):
        mg = cs.skill.item.market_group
        if mg != cur:
            cur = mg
            cur.z_total_sp = 0
            skills[cur] = []

        if cs.points > cs.skill.get_sp_at_level(cs.level):
            cs.z_partial = cs.level + 1

        skills[cur].append(cs)
        cur.z_total_sp += cs.points

    # Retrieve skill queue
    queue = SkillQueue.objects.select_related().filter(character=char).order_by('end_time')

    # Render template
    return render_to_response(
        'thing/character.html',
        {
            'char': char,
            'config': config,
            'skill_loop': range(1, 6),
            'skills': skills,
            'skill_totals': skill_totals,
            'queue': queue,
            'queue_rest': queue[1:],
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Trade volume overview
MONTHS = (None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
@login_required
def trade(request):
    data = {}
    now = datetime.datetime.now()
    
    # Order information
    #orders = Order.objects.filter(corporation=corporation)
    #buy_orders = orders.filter(o_type='B')
    #sell_orders = orders.filter(o_type='S')
    #data['sell_total'] = orders.filter(o_type='S').aggregate(Sum('total_price'))['total_price__sum'] or 0
    #buy_orders = orders.filter(o_type='B')
    #data['buy_total'] = buy_orders.aggregate(Sum('total_price'))['total_price__sum'] or 0
    #data['escrow_total'] = buy_orders.aggregate(Sum('escrow'))['escrow__sum'] or 0
    #data['net_asset_value'] = data['wallet_balance'] + data['sell_total'] + data['escrow_total']
    
    # Transaction stuff oh god
    transactions = Transaction.objects.filter(character__apikey__user=request.user)
    
    t_check = []
    # All
    t_check.append(('[All]', 'all', transactions))
    
    # Campaigns
    for camp in Campaign.objects.filter(user=request.user.id):
        title = '[%s]' % (camp.title)
        t_check.append((title, camp.slug, camp.get_transactions_filter(transactions)))
    
    # Months
    for dt in transactions.dates('date', 'month', order='DESC'):
        name = '%s %s' % (MONTHS[dt.month], dt.year)
        urlpart = '%s-%02d' % (dt.year, dt.month)
        t_check.append((name, urlpart, transactions.filter(date__range=_month_range(dt.year, dt.month))))
    
    # Get data and stuff
    t_data = []
    for name, urlpart, trans in t_check:
        row = { 'name': name, 'urlpart': urlpart }
        
        row['buy_total'] = trans.filter(buy_transaction=True).aggregate(Sum('total_price'))['total_price__sum']
        row['sell_total'] = trans.filter(buy_transaction=False).aggregate(Sum('total_price'))['total_price__sum']
        
        if row['buy_total'] is None or row['sell_total'] is None:
            row['balance'] = 0
        else:
            row['balance'] = row['sell_total'] - row['buy_total']
        
        t_data.append(row)
    
    data['transactions'] = t_data
    
    # Render template
    return render_to_response(
        'thing/trade.html',
        data,
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Trade overview for a variety of timeframe types
@login_required
def trade_timeframe(request, year=None, month=None, period=None, slug=None):
    # Initialise data
    data = {
        'total_buys': 0,
        'total_sells': 0,
        'total_balance': 0,
        'total_projected_average': 0,
        'total_projected_market': 0,
    }
    
    # Get a QuerySet of transactions by this user
    transactions = Transaction.objects.filter(character__apikey__user=request.user)
    
    # Year/Month
    if year and month:
        year = int(year)
        month = int(month)
        transactions = transactions.filter(date__range=_month_range(year, month))
        data['timeframe'] = '%s %s' % (MONTHS[month], year)
        data['urlpart'] = '%s-%02d' % (year, month)
    # Timeframe slug
    elif slug:
        camp = get_object_or_404(Campaign, slug=slug)
        transactions = camp.get_transactions_filter(transactions)
        data['timeframe'] = '%s (%s -> %s)' % (camp.title, camp.start_date, camp.end_date)
        data['urlpart'] = slug
    # All
    elif period:
        data['timeframe'] = 'all time'
        data['urlpart'] = 'all'
    
    # Build aggregate queries to use in our nasty FULL OUTER JOIN
    item_buy_data = transactions.filter(buy_transaction=True).values('item').annotate(
        buy_quantity=Sum('quantity'),
        buy_minimum=Min('price'),
        buy_maximum=Max('price'),
        buy_total=Sum('total_price'),
    )
    item_sell_data = transactions.filter(buy_transaction=False).values('item').annotate(
        sell_quantity=Sum('quantity'),
        sell_minimum=Min('price'),
        sell_maximum=Max('price'),
        sell_total=Sum('total_price'),
    )
    
    # Build a nasty SQL query
    buy_sql = item_buy_data._as_sql(connection)
    sell_sql = item_sell_data._as_sql(connection)
    
    query = queries.trade_timeframe % (buy_sql[0], sell_sql[0])
    params = buy_sql[1] + sell_sql[1]
    
    # Make Item objects out of the nasty query
    data['items'] = []
    for item in Item.objects.raw(query, params):
        # Average profit
        if item.buy_average and item.sell_average:
            item.z_average_profit = item.sell_average - item.buy_average
            item.z_average_profit_per = '%.1f' % (item.z_average_profit / item.buy_average * 100)
        
        # Projected balance
        if item.diff > 0:
            item.z_projected_average = item.balance + (item.diff * item.sell_average)
            item.z_outstanding_average = (item.z_projected_average - item.balance) * -1
            item.z_projected_market = item.balance + (item.diff * item.sell_price)
        else:
            item.z_projected_average = item.balance
            item.z_projected_market = item.balance
        
        data['items'].append(item)
        
        # Update totals
        if item.buy_total is not None:
            data['total_buys'] += item.buy_total
        if item.sell_total is not None:
            data['total_sells'] += item.sell_total
        data['total_projected_average'] += item.z_projected_average
        data['total_projected_market'] += item.z_projected_market
    
    # Totals
    data['total_balance'] = data['total_sells'] - data['total_buys']
    
    # Render template
    return render_to_response(
        'thing/trade_timeframe.html',
        data,
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Transaction list
@login_required
def transactions(request):
    # Get a QuerySet of transactions by this user
    transactions = Transaction.objects.select_related('corp_wallet__corporation', 'item', 'station', 'character').filter(character__apikey__user=request.user).order_by('-date')
    
    # Create a new paginator
    paginator = Paginator(transactions, 100)
    
    # Make sure page request is an int, default to 1st page
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    # If page request is out of range, deliver last page of results
    try:
        transactions = paginator.page(page)
    except (EmptyPage, InvalidPage):
        transactions = paginator.page(paginator.num_pages)
    
    # Render template
    return render_to_response(
        'thing/transactions.html',
        {
            'transactions': transactions,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Transaction details for last x days for specific item
@login_required
def transactions_item(request, item_id, year=None, month=None, period=None, slug=None):
    data = {}
    
    # Get a QuerySet of transactions by this user
    transactions = Transaction.objects.filter(character__apikey__user=request.user).order_by('-date')
    
    # If item_id is an integer we should filter on that item_id
    if item_id.isdigit():
        transactions = transactions.filter(item=item_id)
        data['item'] = Item.objects.get(pk=item_id).name
    else:
        data['item'] = 'all items'
    
    # Year/Month
    if year and month:
        month = int(month)
        transactions = transactions.filter(date__year=year, date__month=month)
        data['timeframe'] = '%s %s' % (MONTHS[month], year)
    # Timeframe slug
    elif slug:
        camp = get_object_or_404(Campaign, slug=slug)
        transactions = camp.get_transactions_filter(transactions)
        data['timeframe'] = '%s (%s -> %s)' % (camp.title, camp.start_date, camp.end_date)
    # All
    else:
        data['timeframe'] = 'all time'
    
    # Create a new paginator
    paginator = Paginator(transactions.select_related('item', 'station', 'character', 'corp_wallet__corporation'), 100)
    
    # Make sure page request is an int, default to 1st page
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    # If page request is out of range, deliver last page of results
    try:
        transactions = paginator.page(page)
    except (EmptyPage, InvalidPage):
        transactions = paginator.page(paginator.num_pages)
    
    data['transactions'] = transactions
    
    # Render template
    return render_to_response(
        'thing/transactions_item.html',
        data,
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Active orders
@login_required
def orders(request):
    # Retrieve orders
    orders = MarketOrder.objects.select_related('item', 'station', 'character', 'corp_wallet__corporation').filter(character__apikey__user=request.user).order_by('station__name', '-buy_order', 'item__name')
    
    # Render template
    return render_to_response(
        'thing/orders.html',
        {
            'orders': orders
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Market scan
@login_required
def market_scan(request):
    cursor = connection.cursor()

    item_ids = []
    cursor.execute(queries.all_item_ids)
    for row in cursor:
        item_ids.append(row[0])

    return render_to_response(
        'thing/market_scan.html',
        {
            'item_ids': item_ids,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Get a range of days for a year/month eg (01, 31)
def _month_range(year, month):
    start = datetime.datetime(year, month, 1)
    end = datetime.datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
    return (start, end)
