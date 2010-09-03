# Create your views here.
import datetime

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.db.models import Avg, Count, Max, Min, Sum
from django.shortcuts import render_to_response, get_object_or_404

from everdi.rdi.models import *


# List of blueprints we own
@login_required
def blueprints(request):
	try:
		runs = int(request.GET.get('runs', '1'))
	except ValueError:
		runs = 1
	
	bpis = []
	for bpi in BlueprintInstance.objects.all().select_related():
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
		})
		bpis[-1]['unit_profit_buy'] = bpis[-1]['market_price'] - bpis[-1]['unit_cost_buy']
		bpis[-1]['unit_profit_sell'] = bpis[-1]['market_price'] - bpis[-1]['unit_cost_sell']
	
	return render_to_response(
		'rdi/blueprints.html',
		{
			'bpis': bpis,
			'runs': runs,
		}
	)

def blueprint_details(request, bpi_id):
	bpi = get_object_or_404(BlueprintInstance, pk=bpi_id)
	components = BlueprintComponent.objects.filter(blueprint=bpi.blueprint)
	
	comps = []
	for component in components:
		comps.append({
			'name': component.item.name,
			'count': component.count,
			'buy_price': component.item.buy_price,
			'buy_total': component.count * component.item.buy_price,
			'sell_price': component.item.sell_price,
			'sell_total': component.count * component.item.sell_price,
		})
	
	buy_total = sum(comp['buy_total'] for comp in comps)
	sell_total = sum(comp['sell_total'] for comp in comps)
	
	return render_to_response(
		'rdi/blueprint_details.html',
		{
			'blueprint_name': bpi.blueprint.name,
			'components': comps,
			'buy_total': buy_total,
			'sell_total': sell_total,
		}
	)

# Trade volume
MONTHS = (None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
@login_required
def trade(request):
	# Check that they have a valid character
	try:
		char = Character.objects.select_related().get(user=request.user)
	except ObjectDoesNotExist:
		return rdi_error("Your account does not have an associated character.")
	if not char.corporation:
		return rdi_error("Your character doesn't seem to be in a corporation.")
	
	data = { 'corporation': char.corporation }
	now = datetime.datetime.now()
	
	# Wallets
	#wallets = CorpWallet.objects.filter(corporation=corporation)
	#if not wallets:
	#	return rdi_error("This corporation has no wallets in the database, run API updater!")
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
		row['class'] = rdi_balance_class(row['balance'])
		
		t_data.append(row)
	
	data['transactions'] = t_data
	
	return render_to_response('rdi/trade.html', data)

# Trade overview for a variety of timeframe types
@login_required
def trade_timeframe(request, year=None, month=None, period=None, slug=None):
	# Check that they have a valid character
	try:
		char = Character.objects.select_related().get(user=request.user)
	except ObjectDoesNotExist:
		return rdi_error("Your account does not have an associated character.")
	if not char.corporation:
		return rdi_error("Your character doesn't seem to be in a corporation.")
	
	data = { 'corporation': char.corporation }
	now = datetime.datetime.now()
	
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
			return rdi_error("Invalid timeframe slug.")
		transactions = transactions.filter(date__range=(tf[0].start_date, tf[0].end_date))
		data['timeframe'] = '%s (%s -> %s)' % (tf[0].title, tf[0].start_date, tf[0].end_date)
		data['urlpart'] = slug
	# All
	elif period:
		data['timeframe'] = 'all time'
		data['urlpart'] = 'all'
	
	# Do aggregate queries now instead of doing 2 per item type
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
	
	# And uhh combine them
	item_data = {}
	for row in item_buy_data:
		item_data[row['item']] = row
	for row in item_sell_data:
		item_data.setdefault(row['item'], {}).update(row)
	
	# Get the shorter names - yuck!
	for item_id, item in Item.objects.in_bulk([row['item'] for row in item_data.values()]).items():
		item_data[item_id]['shorter_name'] = item.shorter_name()
	
	# Start gathering data
	data['items'] = []
	for item_row in item_data.values():
		# Averages
		if 'buy_quantity' in item_row:
			item_row['buy_average'] = (item_row['buy_total'] / item_row['buy_quantity']).quantize(Decimal('.01'), rounding=ROUND_UP)
		else:
			item_row['buy_average'] = 0
		if 'sell_quantity' in item_row:
			item_row['sell_average'] = (item_row['sell_total'] / item_row['sell_quantity']).quantize(Decimal('.01'), rounding=ROUND_UP)
		else:
			item_row['sell_average'] = 0
		
		# Average profit
		if item_row['buy_average'] and item_row['sell_average']:
			item_row['average_profit'] = item_row['sell_average'] - item_row['buy_average']
			item_row['average_profit_per'] = Decimal('%.1f' % (item_row['average_profit'] / item_row['buy_average'] * 100))
		# Balance
		item_row['balance'] = item_row.get('sell_total', 0) - item_row.get('buy_total', 0)
		item_row['balance_class'] = rdi_balance_class(item_row['balance'])
		# Projected balance
		diff = item_row.get('buy_quantity', 0) - item_row.get('sell_quantity', 0)
		if diff > 0:
			item_row['projected'] = item_row['balance'] + (diff * item_row['sell_average'])
		else:
			item_row['projected'] = item_row['balance']
		item_row['projected_class'] = rdi_balance_class(item_row['projected'])
		
		data['items'].append(item_row)
	
	# Totals
	data['total_buys'] = sum(item.get('buy_total', 0) for item in data['items'])
	data['total_sells'] = sum(item.get('sell_total', 0) for item in data['items'])
	data['total_balance'] = data['total_sells'] - data['total_buys']
	data['total_balance_class'] = rdi_balance_class(data['total_balance'])
	data['total_projected'] = sum(item['projected'] for item in data['items'])
	data['total_projected_class'] = rdi_balance_class(data['total_projected'])
	
	# GENERATE
	return render_to_response('rdi/trade_timeframe.html', data)


# Corp transaction details
@login_required
def transactions(request):
	# Check that they have a valid character
	try:
		char = Character.objects.select_related().get(user=request.user)
	except ObjectDoesNotExist:
		return rdi_error("Your account does not have an associated character.")
	if not char.corporation:
		return rdi_error("Your character doesn't seem to be in a corporation.")
	
	# See if this corp has any transactions
	transactions = Transaction.objects.filter(corporation=char.corporation).order_by('date').reverse()
	if transactions.count() == 0:
		return rdi_error("There are no transactions for your corporation.")
	
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
	return render_to_response('rdi/transactions.html', { 'transactions': transactions })

# Corp transaction details for last x days for specific item
@login_required
def transactions_item(request, item_id, year=None, month=None, period=None, slug=None):
	# Check that they have a valid character
	try:
		char = Character.objects.select_related().get(user=request.user)
	except ObjectDoesNotExist:
		return rdi_error("Your account does not have an associated character.")
	if not char.corporation:
		return rdi_error("Your character doesn't seem to be in a corporation.")
	
	# Make sure item_id is valid
	data = {}
	
	if item_id.isdigit():
		transactions = Transaction.objects.filter(corporation=char.corporation, item=item_id).order_by('date').reverse()
	else:
		transactions = Transaction.objects.order_by('date').reverse()
		data['item'] = 'all items'
	
	if transactions.count() == 0:
		return rdi_error("There are no transactions matching those criteria.")
	
	if 'item' not in data:
		data['item'] = transactions[0].item.name
	
	# Year/Month
	if year and month:
		month = int(month)
		data['transactions'] = transactions.filter(date__year=year, date__month=month)
		data['timeframe'] = '%s %s' % (MONTHS[month], year)
	# Timeframe slug
	elif slug:
		tf = Timeframe.objects.filter(corporation=char.corporation, slug=slug)
		if tf.count() == 0:
			return rdi_error("Invalid timeframe slug.")
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
	return render_to_response('rdi/transactions_item.html', data)

# Active orders
@login_required
def orders(request):
	# Check that they have a valid character
	try:
		char = Character.objects.select_related().get(user=request.user)
	except ObjectDoesNotExist:
		return rdi_error("Your account does not have an associated character.")
	if not char.corporation:
		return rdi_error("Your character doesn't seem to be in a corporation.")
	
	# Retrieve orders
	orders = Order.objects.filter(corporation=char.corporation).select_related()
	
	return render_to_response('rdi/orders.html', { 'orders': orders })


def rdi_error(error_msg):
	return render_to_response('rdi/error.html', { 'error': error_msg })

def rdi_balance_class(balance):
	if balance > 0:
		return ' class="g"'
	elif balance < 0:
		return ' class="r"'
	else:
		return ''
