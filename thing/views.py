import datetime
#import time

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.db import connection
from django.db.models import Avg, Count, Max, Min, Sum
from django.shortcuts import render_to_response, get_object_or_404

from evething.thing.models import *


# I hope one day I can do this sanely via Django ORM :p
TRADE_TIMEFRAME_JOIN = """
SELECT
  COALESCE(t1.item_id, t2.item_id) AS id,
  i.name,
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
ORDER BY balance DESC
"""


# List of blueprints we own
@login_required
def blueprints(request):
	# Check that they have a valid character
	chars = Character.objects.select_related().filter(user=request.user)
	if chars.count() == 0:
		return show_error("Your account does not have an associated character.")
	if not chars[0].corporation:
		return show_error("Your first character doesn't seem to be in a corporation, what the hell?")
	
	try:
		runs = int(request.GET.get('runs', '1'))
	except ValueError:
		runs = 1
	
	bpis = []
	for bpi in BlueprintInstance.objects.select_related().filter(character__corporation=chars[0].corporation):
		bpis.append({
			'character': bpi.character,
			'id': bpi.id,
			'blueprint': bpi.blueprint,
			'type': bpi.get_bp_type_display(),
			'material_level': bpi.material_level,
			'productivity_level': bpi.productivity_level,
			'count': bpi.blueprint.item.portion_size * runs,
			'production_time': bpi.calc_production_time(runs=runs),
			'unit_cost_buy': bpi.calc_production_cost(runs=runs),
			'unit_cost_sell': bpi.calc_production_cost(runs=runs, use_sell=True),
			'market_price': bpi.blueprint.item.sell_price,
			'components': bpi._get_components(runs=runs),
		})
		bpis[-1]['unit_profit_buy'] = bpis[-1]['market_price'] - bpis[-1]['unit_cost_buy']
		bpis[-1]['unit_profit_sell'] = bpis[-1]['market_price'] - bpis[-1]['unit_cost_sell']
	
	return render_to_response(
		'thing/blueprints.html',
		{
			'bpis': bpis,
			'runs': runs,
		}
	)

# Calculate blueprint production details for X number of days
DAY = 24 * 60 * 60
@login_required
def bpcalc(request):
	# Check that they have a valid character
	chars = Character.objects.select_related().filter(user=request.user)
	if chars.count() == 0:
		return show_error("Your account does not have an associated character.")
	if not chars[0].corporation:
		return show_error("Your first character doesn't seem to be in a corporation, what the hell?")
	
	# Get a valid number of days
	try:
		days = int(request.GET.get('days', '7'))
	except ValueError:
		days = 7
	
	# Get provided BlueprintInstance ids
	bpi_ids = []
	for k in request.GET:
		if k.startswith('bpi') and k[3:].isdigit():
			bpi_ids.append(k[3:])
	
	# Fetch BlueprintInstance objects
	bpis = []
	comps = {}
	final_items = []
	for bpi in BlueprintInstance.objects.select_related().filter(character__corporation=chars[0].corporation).in_bulk(bpi_ids).values():
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
		# And the final item
		final_items.append(bpi.blueprint.item.id)
		
		bpc = bpi.calc_production_cost(runs=runs, components=components)
		spc = bpi.calc_production_cost(runs=runs, use_sell=True, components=components)
		
		bpis.append({
			'item': bpi.blueprint.item,
			'name': bpi.blueprint.name,
			'total_time': pt * runs,
			'runs': runs,
			'built': built,
			'sell': bpi.blueprint.item.sell_price * built,
			'buy_build': bpc * built,
			'sell_build': spc * built,
			'volume_week': bpi.blueprint.item.get_volume(),
		})
		row = bpis[-1]
		row['buy_profit'] = row['sell'] - row['buy_build']
		row['buy_profit_per'] = (row['buy_profit'] / row['buy_build'] * 100).quantize(Decimal('.1'))
		row['sell_profit'] = row['sell'] - row['sell_build']
		row['sell_profit_per'] = (row['sell_profit'] / row['sell_build'] * 100).quantize(Decimal('.1'))
		if row['volume_week']:
			row['volume_percent'] = (row['built'] / row['volume_week'] * 100).quantize(Decimal('.1'))
	
	bpis.sort(key=lambda b: b['sell_profit'])
	bpis.reverse()
	
	# Yeah this is awful, but better than using 95000 queries... right? :|
	# FIXME:this might work, but adding the data to the bpis list will be awfully slow. Think on it.
	#filler = []
	#for fi in final_items:
	#	filler.append('(SELECT item_id, movement FROM thing_itempricehistory WHERE item_id = %s ORDER BY date DESC LIMIT 7)' % (fi))
	#
	#query = """SELECT item_id, SUM(movement) FROM
	#(%s) AS blah
	#GROUP BY item_id""" % (' UNION ALL '.join(filler))
	#cursor = connection.cursor()
	#cursor.execute(query)
	#for k,v in cursor.fetchall():
	
	# Components
	components = []
	for item, amt in comps.items():
		components.append({
			'item': item,
			'amount': amt,
			'volume': (amt * item.volume).quantize(Decimal('.1')),
			'buy_total': amt * item.buy_price,
			'sell_total': amt * item.sell_price,
		})
	components.sort(key=lambda c: c['item'].name)
	
	# Do some sums
	bpi_totals = {
		'sell': sum(bpi['sell'] for bpi in bpis),
		'buy_build': sum(bpi['buy_build'] for bpi in bpis),
		'buy_profit': sum(bpi['buy_profit'] for bpi in bpis),
		'sell_build': sum(bpi['sell_build'] for bpi in bpis),
		'sell_profit': sum(bpi['sell_profit'] for bpi in bpis),
	}
	bpi_totals['buy_profit_per'] = (bpi_totals['buy_profit'] / bpi_totals['buy_build'] * 100).quantize(Decimal('.1'))
	bpi_totals['sell_profit_per'] = (bpi_totals['sell_profit'] / bpi_totals['sell_build'] * 100).quantize(Decimal('.1'))
	comp_totals = {
		'volume': sum(comp['volume'] for comp in components),
		'buy_total': sum(comp['buy_total'] for comp in components),
		'sell_total': sum(comp['sell_total'] for comp in components),
	}
	
	return render_to_response(
		'thing/bpcalc.html',
		{
			'bpis': bpis,
			'bpi_totals': bpi_totals,
			'components': components,
			'comp_totals': comp_totals,
		}
	)

# Trade volume
MONTHS = (None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
@login_required
def trade(request):
	# Check that they have a valid character
	chars = Character.objects.select_related().filter(user=request.user)
	if chars.count() == 0:
		return show_error("Your account does not have an associated character.")
	if not chars[0].corporation:
		return show_error("Your first character doesn't seem to be in a corporation, what the hell?")
	
	data = { 'corporation': chars[0].corporation }
	now = datetime.datetime.now()
	
	# Wallets
	#wallets = CorpWallet.objects.filter(corporation=corporation)
	#if not wallets:
	#	return show_error("This corporation has no wallets in the database, run API updater!")
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
	transactions = Transaction.objects.filter(corporation=data['corporation'])
	
	t_check = []
	# All
	t_check.append(('[All]', 'all', transactions))
	#t_check.append('-')
	# Timeframes
	for tf in Timeframe.objects.filter(corporation=data['corporation']):
		title = '[%s]' % (tf.title)
		t_check.append((title, tf.slug, transactions.filter(date__range=(tf.start_date, tf.end_date))))
	#if len(t_check) > 2:
	#	t_check.append('-')
	# Months
	for dt in transactions.dates('date', 'month', order='DESC'):
		name = '%s %s' % (MONTHS[dt.month], dt.year)
		urlpart = '%s-%02d' % (dt.year, dt.month)
		t_check.append((name, urlpart, transactions.filter(date__month=dt.month)))
	
	# Get data and stuff
	t_data = []
	for name, urlpart, trans in t_check:
		row = { 'name': name, 'urlpart': urlpart }
		
		row['buy_total'] = trans.filter(t_type='B').aggregate(Sum('total_price'))['total_price__sum']
		row['sell_total'] = trans.filter(t_type='S').aggregate(Sum('total_price'))['total_price__sum']
		
		if row['buy_total'] is None or row['sell_total'] is None:
			row['balance'] = 0
		else:
			row['balance'] = row['sell_total'] - row['buy_total']
		
		t_data.append(row)
	
	data['transactions'] = t_data
	
	return render_to_response('thing/trade.html', data)

# Trade overview for a variety of timeframe types
@login_required
def trade_timeframe(request, year=None, month=None, period=None, slug=None):
	#times = []
	#times.append((time.time(), 'start'))
	
	# Check that they have a valid character
	chars = Character.objects.select_related().filter(user=request.user)
	if chars.count() == 0:
		return show_error("Your account does not have an associated character.")
	if not chars[0].corporation:
		return show_error("Your first character doesn't seem to be in a corporation, what the hell?")
	
	data = { 'corporation': chars[0].corporation }
	now = datetime.datetime.now()
	
	#times.append((time.time(), 'charcheck'))
	
	# Get a QuerySet of transactions for this corporation
	transactions = Transaction.objects.filter(corporation=data['corporation'])
	
	# Year/Month
	if year and month:
		month = int(month)
		transactions = transactions.filter(date__year=year, date__month=month)
		data['timeframe'] = '%s %s' % (MONTHS[month], year)
		data['urlpart'] = '%s-%02d' % (year, month)
	# Timeframe slug
	elif slug:
		tf = Timeframe.objects.filter(corporation=data['corporation'], slug=slug)
		if not tf:
			return show_error("Invalid timeframe slug.")
		transactions = transactions.filter(date__range=(tf[0].start_date, tf[0].end_date))
		data['timeframe'] = '%s (%s -> %s)' % (tf[0].title, tf[0].start_date, tf[0].end_date)
		data['urlpart'] = slug
	# All
	elif period:
		data['timeframe'] = 'all time'
		data['urlpart'] = 'all'
	
	#times.append((time.time(), 'yearmonth'))
	
	# Build aggregate queries to use in our nasty FULL OUTER JOIN
	item_buy_data = transactions.filter(t_type='B').values('item').annotate(
		buy_quantity=Sum('quantity'),
		buy_minimum=Min('price'),
		buy_maximum=Max('price'),
		buy_total=Sum('total_price'),
	)
	item_sell_data = transactions.filter(t_type='S').values('item').annotate(
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
	
	# And make Item objects out of it
	item_data = Item.objects.raw(query, params)
	
	#times.append((time.time(), 'combine'))
	
	# Start gathering data
	data['items'] = []
	for item in item_data:
		item_row = { 'item': item }
		
		# Average profit
		if item.buy_average and item.sell_average:
			item_row['average_profit'] = item.sell_average - item.buy_average
			item_row['average_profit_per'] = Decimal('%.1f' % (item_row['average_profit'] / item.buy_average * 100))
		# Projected balance
		if item.diff > 0:
			item_row['projected_average'] = item.balance + (item.diff * item.sell_average)
			item_row['outstanding_average'] = item_row['projected_average'] - item.balance
			if item.sell_price:
				item_row['projected_market'] = item.balance + (item.diff * item.sell_price)
		else:
			item_row['projected_average'] = item.balance
			item_row['projected_market'] = item.balance
		
		data['items'].append(item_row)
	
	#times.append((time.time(), 'gather'))
	
	# Totals
	data['total_buys'] = sum(item_row['item'].buy_total for item_row in data['items'] if item_row['item'].buy_total)
	data['total_sells'] = sum(item_row['item'].sell_total for item_row in data['items'] if item_row['item'].sell_total)
	data['total_balance'] = data['total_sells'] - data['total_buys']
	data['total_projected_average'] = sum(item_row['projected_average'] for item_row in data['items'])
	data['total_projected_market'] = sum(item_row.get('projected_market', 0) for item_row in data['items'])
	
	#times.append((time.time(), 'totals'))
	#for i in range(len(times) - 1):
	#	print '%s: %.5f' % (times[i+1][1], times[i+1][0] - times[i][0])
	
	# GENERATE
	return render_to_response('thing/trade_timeframe.html', data)


# Corp transaction details
@login_required
def transactions(request):
	# Check that they have a valid character
	chars = Character.objects.select_related().filter(user=request.user)
	if chars.count() == 0:
		return show_error("Your account does not have an associated character.")
	if not chars[0].corporation:
		return show_error("Your first character doesn't seem to be in a corporation, what the hell?")
	
	# See if this corp has any transactions
	transactions = Transaction.objects.select_related('item', 'station').filter(corporation=chars[0].corporation).order_by('date').reverse()
	if transactions.count() == 0:
		return show_error("There are no transactions for your corporation.")
	
	# Paginator stuff
	paginator = Paginator(transactions, 100)
	
	# Make sure page request is an int. If not, deliver first page.
	try:
		page = int(request.GET.get('page', '1'))
	except ValueError:
		page = 1
	
	# If page request (9999) is out of range, deliver last page of results.
	try:
		transactions = paginator.page(page)
	except (EmptyPage, InvalidPage):
		transactions = paginator.page(paginator.num_pages)
	
	# Spit it out I guess
	return render_to_response('thing/transactions.html', { 'transactions': transactions })

# Corp transaction details for last x days for specific item
@login_required
def transactions_item(request, item_id, year=None, month=None, period=None, slug=None):
	# Check that they have a valid character
	chars = Character.objects.select_related().filter(user=request.user)
	if chars.count() == 0:
		return show_error("Your account does not have an associated character.")
	if not chars[0].corporation:
		return show_error("Your first character doesn't seem to be in a corporation, what the hell?")
	
	# Make sure item_id is valid
	data = {}
	
	if item_id.isdigit():
		transactions = Transaction.objects.filter(corporation=chars[0].corporation, item=item_id).order_by('date').reverse()
	else:
		transactions = Transaction.objects.order_by('date').reverse()
		data['item'] = 'all items'
	
	if transactions.count() == 0:
		return show_error("There are no transactions matching those criteria.")
	
	if 'item' not in data:
		data['item'] = transactions[0].item.name
	
	# Year/Month
	if year and month:
		month = int(month)
		data['transactions'] = transactions.filter(date__year=year, date__month=month)
		data['timeframe'] = '%s %s' % (MONTHS[month], year)
	# Timeframe slug
	elif slug:
		tf = Timeframe.objects.filter(corporation=chars[0].corporation, slug=slug)
		if tf.count() == 0:
			return show_error("Invalid timeframe slug.")
		transactions = transactions.filter(date__range=(tf[0].start_date, tf[0].end_date))
		data['timeframe'] = '%s (%s -> %s)' % (tf[0].title, tf[0].start_date, tf[0].end_date)
	# All
	elif period:
		data['timeframe'] = 'all time'
	else:
		data['timeframe'] = 'all time'
	
	# Paginator stuff
	paginator = Paginator(transactions, 100)
	
	# Make sure page request is an int. If not, deliver first page.
	try:
		page = int(request.GET.get('page', '1'))
	except ValueError:
		page = 1
	
	# If page request (9999) is out of range, deliver last page of results.
	try:
		transactions = paginator.page(page)
	except (EmptyPage, InvalidPage):
		transactions = paginator.page(paginator.num_pages)
	
	data['transactions'] = transactions
	
	# Spit it out I guess
	return render_to_response('thing/transactions_item.html', data)

# Active orders
@login_required
def orders(request):
	# Check that they have a valid character
	chars = Character.objects.select_related().filter(user=request.user)
	if chars.count() == 0:
		return show_error("Your account does not have an associated character.")
	if not chars[0].corporation:
		return show_error("Your first character doesn't seem to be in a corporation, what the hell?")
	
	# Retrieve orders
	orders = Order.objects.select_related().filter(corporation=chars[0].corporation)
	
	return render_to_response('thing/orders.html', { 'orders': orders })


def show_error(error_msg):
	return render_to_response('thing/error.html', { 'error': error_msg })

def get_balance_class(balance):
	if balance > 0:
		return ' class="g"'
	elif balance < 0:
		return ' class="r"'
	else:
		return ''
