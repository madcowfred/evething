import calendar
import datetime
#import time

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.db import connection
from django.db.models import Avg, Count, Max, Min, Sum
from django.shortcuts import *
from django.template import RequestContext

from evething.thing.models import *


# This is the nasty trade timeframe thing. Be afraid.
# I hope one day I can do this via the Django ORM :p
TRADE_TIMEFRAME_JOIN = """
SELECT
  COALESCE(t1.item_id, t2.item_id) AS id,
  i.name,
  ic.name AS cat_name,
  i.sell_price,
  t1.buy_maximum, t1.buy_quantity, t1.buy_total, t1.buy_minimum,
  t2.sell_maximum, t2.sell_quantity, t2.sell_total, t2.sell_minimum,
  t1.buy_total / t1.buy_quantity AS buy_average,
  t2.sell_total / t2.sell_quantity AS sell_average,
  COALESCE(t2.sell_total, 0) - COALESCE(t1.buy_total, 0) AS balance,
  t1.buy_quantity - t2.sell_quantity AS diff
FROM
(
  %s
) t1
FULL OUTER JOIN
(
  %s
) t2
ON t1.item_id = t2.item_id
INNER JOIN thing_item i
ON i.id = COALESCE(t1.item_id, t2.item_id)
INNER JOIN thing_itemgroup ig
ON i.item_group_id = ig.id
INNER JOIN thing_itemcategory ic
ON ig.category_id = ic.id
"""


@login_required
def home(request):
    return render_to_response(
        'thing/home.html',
        context_instance=RequestContext(request)
    )

# List of blueprints we own
@login_required
def blueprints(request):
    # Get a valid number of runs
    try:
        runs = int(request.GET.get('runs', '1'))
    except ValueError:
        runs = 1
    
    # Assemble blueprint data
    bpis = []
    for bpi in BlueprintInstance.objects.select_related().filter(user=request.user.id):
        # Cache component list so we don't have to retrieve it multiple times
        components = bpi._get_components(runs=runs)
        
        # Calculate a bunch of things we can't easily do via SQL
        bpi.z_count = bpi.blueprint.item.portion_size * runs
        bpi.z_production_time = bpi.calc_production_time(runs=runs)
        bpi.z_unit_cost_buy = bpi.calc_production_cost(runs=runs, components=components)
        bpi.z_unit_profit_buy = bpi.blueprint.item.sell_price - bpi.z_unit_cost_buy
        bpi.z_unit_cost_sell = bpi.calc_production_cost(runs=runs, use_sell=True, components=components)
        bpi.z_unit_profit_sell = bpi.blueprint.item.sell_price - bpi.z_unit_cost_sell
        
        bpis.append(bpi)
    
    # Render template
    return render_to_response(
        'thing/blueprints.html',
        {
            'bpis': bpis,
            'runs': runs,
        },
        context_instance=RequestContext(request)
    )

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
        comps = {}
        # Fetch BlueprintInstance objects
        for bpi in BlueprintInstance.objects.select_related().filter(user=request.user.id, pk__in=bpi_list):
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
            components = bpi._get_components(runs=runs)
            for item, amt in components:
                comps[item] = comps.get(item, 0) + amt
            
            # Calculate a bunch of things we can't easily do via SQL
            bpi.z_total_time = pt * runs
            bpi.z_runs = runs
            bpi.z_built = built
            bpi.z_total_sell = bpi.blueprint.item.sell_price * built
            bpi.z_buy_build = bpi.calc_production_cost(runs=runs, components=components) * built
            bpi.z_sell_build = bpi.calc_production_cost(runs=runs, use_sell=True, components=components) * built
            bpi.z_volume_week = bpi.blueprint.item.get_volume()
            if bpi.z_volume_week:
                bpi.z_volume_percent = (bpi.z_built / bpi.z_volume_week * 100).quantize(Decimal('.1'))
            
            bpi.z_buy_profit = bpi.z_total_sell - bpi.z_buy_build
            bpi.z_buy_profit_per = (bpi.z_buy_profit / bpi.z_buy_build * 100).quantize(Decimal('.1'))
            bpi.z_sell_profit = bpi.z_total_sell - bpi.z_sell_build
            bpi.z_sell_profit_per = (bpi.z_sell_profit / bpi.z_sell_build * 100).quantize(Decimal('.1'))
            
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

# Trade volume
MONTHS = (None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
@login_required
def trade(request):
    data = {}
    now = datetime.datetime.now()
    
    # Wallets
    #wallets = CorpWallet.objects.filter(corporation=corporation)
    #if not wallets:
    #    return show_error("This corporation has no wallets in the database, run API updater!")
    #
    #data['wallets'] = wallets
    #data['wallet_balance'] = wallets.aggregate(Sum('balance'))['balance__sum'] or 0
    
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
    transactions = Transaction.objects.filter(character__apikey__user=request.user.id)
    
    t_check = []
    # All
    t_check.append(('[All]', 'all', transactions))
    
    # Campaigns
    for camp in Campaign.objects.filter(user=request.user.id):
        title = '[%s]' % (camp.title)
        t_check.append((title, camp.slug, transactions.filter(date__range=(camp.start_date, camp.end_date))))
    
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
    transactions = Transaction.objects.filter(character__apikey__user=request.user.id)
    
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
        transactions = transactions.filter(date__range=(camp.start_date, camp.end_date))
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
    
    query = TRADE_TIMEFRAME_JOIN % (buy_sql[0], sell_sql[0])
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


# Corp transaction details
@login_required
def transactions(request):
    # Get a QuerySet of transactions by this user
    #transactions = Transaction.objects.select_related('corp_wallet', 'item', 'station', 'character').filter(character__apikey__user=request.user.id).order_by('-date')
    #transactions = Transaction.objects.select_related(depth=2).filter(character__apikey__user=request.user.id).order_by('-date')
    transactions = Transaction.objects.select_related('corp_wallet__corporation', 'item', 'station', 'character').filter(character__apikey__user=request.user.id).order_by('-date')
    
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

# Corp transaction details for last x days for specific item
@login_required
def transactions_item(request, item_id, year=None, month=None, period=None, slug=None):
    data = {}
    
    # Get a QuerySet of transactions by this user
    transactions = Transaction.objects.filter(character__apikey__user=request.user.id).order_by('-date')
    
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
        tf = get_object_or_404(Timeframe, slug=slug)
        transactions = transactions.filter(date__range=(tf.start_date, tf.end_date))
        data['timeframe'] = '%s (%s -> %s)' % (tf.title, tf.start_date, tf.end_date)
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

# Active orders
@login_required
def orders(request):
    # Retrieve orders
    orders = MarketOrder.objects.select_related('item', 'station', 'character', 'corp_wallet__corporation').filter(character__apikey__user=request.user.id).order_by('buy_order', 'station__name', 'item__name')
    
    # Render template
    return render_to_response(
        'thing/orders.html',
        {
            'orders': orders
        },
        context_instance=RequestContext(request)
    )


def _month_range(year, month):
    start = datetime.datetime(year, month, 1)
    end = datetime.datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
    return (start, end)
