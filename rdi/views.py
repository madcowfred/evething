# Create your views here.
import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from django.db.models import Avg, Count, Max, Min, Sum

from everdi.rdi.models import *


# List of blueprints we own
@login_required
def blueprints(request):
	runs = request.GET.get('runs')
	if runs and runs.isdigit():
		runs = int(runs)
	else:
		runs = 1
	
	bpis = []
	for bpi in BlueprintInstance.objects.all():
		bpis.append({
			'character': bpi.character,
			'id': bpi.id,
			'blueprint': bpi.blueprint,
			'material_level': bpi.material_level,
			'productivity_level': bpi.productivity_level,
			'count': bpi.blueprint.item.portion_size * runs,
			'production_time': bpi.calc_production_time(runs=runs),
			'unit_cost_buy': bpi.calc_production_cost(runs=runs),
			'unit_cost_sell': bpi.calc_production_cost(runs=runs, use_sell=True),
			'market_price': bpi.blueprint.item.sell_price,
		})
	
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
	
	buy_total = 0
	sell_total = 0
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
		buy_total += comps[-1]['buy_total']
		sell_total += comps[-1]['sell_total']
	
	return render_to_response(
		'rdi/blueprint_details.html',
		{
			'blueprint_name': bpi.blueprint.name,
			'components': comps,
			'buy_total': buy_total,
			'sell_total': sell_total,
		}
	)

# Corp finances
MONTHS = (None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
@login_required
def trade(request):
	# Check that they have a valid character
	chars = Character.objects.filter(user=request.user)
	if not chars:
		return rdi_error("You do not have a character defined.")
	if not chars[0].corporation:
		return rdi_error("Your character doesn't seem to be in a corporation.")
	
	corporation = chars[0].corporation
	data = { 'corporation': corporation }
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
	transactions = Transaction.objects.filter(corporation=corporation)
	
	t_check = []
	# All
	t_check.append(('[All]', 'all', transactions))
	#t_check.append('-')
	# Timeframes
	for tf in Timeframe.objects.filter(corporation=corporation):
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

# Corp transaction overview for a variety of timeframe types
@login_required
def trade_timeframe(request, year=None, month=None, period=None, slug=None):
	# Check that they have a valid character
	chars = Character.objects.filter(user=request.user)
	if not chars:
		return rdi_error("You do not have a character defined.")
	if not chars[0].corporation:
		return rdi_error("Your character doesn't seem to be in a corporation.")
	
	corporation = chars[0].corporation
	data = { 'corporation': corporation }
	now = datetime.datetime.now()
	
	# Get a QuerySet of transactions for this corporationj
	transactions = Transaction.objects.filter(corporation=corporation)
	
	# Year/Month
	if year and month:
		month = int(month)
		transactions = transactions.filter(date__year=year, date__month=month)
		data['timeframe'] = '%s %s' % (MONTHS[month], year)
		data['urlpart'] = '%s-%02d' % (year, month)
	# Timeframe slug
	elif slug:
		tf = Timeframe.objects.filter(corporation=corporation, slug=slug)
		if not tf:
			return rdi_error("Invalid timeframe slug.")
		transactions = transactions.filter(date__range=(tf[0].start_date, tf[0].end_date))
		data['timeframe'] = '%s (%s -> %s)' % (tf[0].title, tf[0].start_date, tf[0].end_date)
		data['urlpart'] = slug
	# All
	elif period:
		data['timeframe'] = 'all time'
		data['urlpart'] = 'all'
	
	# Get distinct item ids
	item_ids = transactions.values_list('item').distinct()
	if not item_ids:
		return rdi_error("There are no transactions or something, idk.")
	
	# Start gathering data
	data['items'] = []
	for item_id in item_ids:
		iid = item_id[0]
		item_data = { 'item': Item.objects.filter(pk=iid)[0] }
		
		t = transactions.filter(item=iid)
		t_buy = t.filter(t_type='B')
		if not t_buy:
			continue
		t_sell = t.filter(t_type='S')
		if not t_sell:
			continue
		
		# Buy data, urgh
		item_data.update(t_buy.aggregate(
			buy_quantity=Sum('quantity'),
			buy_minimum=Min('price'),
			buy_maximum=Max('price'),
			buy_total=Sum('total_price'),
		))
		item_data['buy_average'] = (item_data['buy_total'] / item_data['buy_quantity']).quantize(Decimal('.01'), rounding=ROUND_UP)
		
		# Sell data, urgh
		item_data.update(t_sell.aggregate(
			sell_quantity=Sum('quantity'),
			sell_minimum=Min('price'),
			sell_maximum=Max('price'),
			sell_total=Sum('total_price'),
		))
		item_data['sell_average'] = (item_data['sell_total'] / item_data['sell_quantity']).quantize(Decimal('.01'), rounding=ROUND_UP)
		
		# Average profit
		item_data['average_profit'] = item_data['sell_average'] - item_data['buy_average']
		item_data['average_profit_per'] = Decimal('%.1f' % (item_data['average_profit'] / item_data['buy_average'] * 100))
		# Balance
		item_data['balance'] = item_data['sell_total'] - item_data['buy_total']
		item_data['balance_class'] = rdi_balance_class(item_data['balance'])
		# Projected balance
		diff = item_data['buy_quantity'] - item_data['sell_quantity']
		if diff > 0:
			item_data['projected'] = item_data['balance'] + (diff * item_data['sell_average'])
		else:
			item_data['projected'] = item_data['balance']
		item_data['projected_class'] = rdi_balance_class(item_data['projected'])
		
		data['items'].append(item_data)
	
	# Ugh turn it into a sorted by balance list
	data['items'].sort(key=lambda a: a['balance'])
	data['items'].reverse()
	
	# GENERATE
	return render_to_response('rdi/trade_timeframe.html', data)


# Corp transaction details
@login_required
def transactions(request):
	return rdi_error('Not yet implemented.')

# Corp transaction details for last x days for specific item
@login_required
def transactions_item(request, timeframe, item_id):
	# Check that they have a valid character
	chars = Character.objects.filter(user=request.user)
	if not chars:
		return rdi_error("You do not have a character defined.")
	if not chars[0].corporation:
		return rdi_error("Your character doesn't seem to be in a corporation.")
	
	corporation = chars[0].corporation
	
	# Sanity check
	days = DAYS[timeframe]
	item_id = int(item_id)
	
	# Make sure item_id is valid
	transactions = Transaction.objects.filter(corporation=corporation, item=item_id).order_by('date').reverse()
	if not transactions:
		return rdi_error("There are no transactions for that item_id.")
	
	data = {
		'days': days,
		'item': transactions[0].item.name,
		'transactions': transactions,
	}
	
	# Spit it out I guess
	return render_to_response('rdi/transactions_item.html', data)

# Active orders
@login_required
def orders(request):
	# Check that they have a valid character
	chars = Character.objects.filter(user=request.user)
	if not chars:
		return rdi_error("You do not have a character defined.")
	if not chars[0].corporation:
		return rdi_error("Your character doesn't seem to be in a corporation.")
	
	corporation = chars[0].corporation
	
	# Retrieve orders
	orders = Order.objects.filter(corporation=corporation)
	
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
