# Create your views here.
import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from django.db.models import Avg, Count, Max, Min, Sum

from everdi.rdi.models import *


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
			'market_price': bpi.blueprint.item.sell_median,
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
			'buy_median': component.item.buy_median,
			'buy_total': component.count * component.item.buy_median,
			'sell_median': component.item.sell_median,
			'sell_total': component.count * component.item.sell_median,
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

# Corp main page
@login_required
def finances(request):
	# Check that they have a valid character
	chars = Character.objects.filter(user=request.user)
	if not chars:
		return "You do not have a character defined."
	if not chars[0].corporation:
		return "Your character doesn't seem to be in a corporation."
	
	corporation = chars[0].corporation
	data = { 'corporation': corporation }
	now = datetime.datetime.now()
	
	# Wallets
	wallets = CorpWallet.objects.filter(corporation=corporation)
	if not wallets:
		return rdi_error("'%s' has no corporation wallets in the database, run api_updater.py!" % (corporation.name))
	
	data['wallets'] = wallets
	data['wallet_balance'] = wallets.aggregate(Sum('balance'))['balance__sum']
	
	# Transaction volume recently
	for days in (1, 7, 30, 9999):
		checkdate = now - datetime.timedelta(days)
		transactions = Transaction.objects.filter(date__gt=checkdate)
		
		buy_total = transactions.filter(t_type='B').aggregate(Sum('total_price'))['total_price__sum']
		data['%sday_buy_total' % days] = buy_total
		
		sell_total = transactions.filter(t_type='S').aggregate(Sum('total_price'))['total_price__sum']
		data['%sday_sell_total' % days] = sell_total
		
		if buy_total is None or sell_total is None:
			balance = 0
		else:
			balance = sell_total - buy_total
		
		data['%sday_balance' % days] = balance
		data['%sday_class' % days] = rdi_balance_class(balance)
	
	
	return render_to_response('rdi/finances.html', data)

# Corp transaction overview for last x days
DAYS = {
	'day': 1,
	'week': 7,
	'month': 30,
	'all': 9999,
}
@login_required
def finances_timeframe(request, timeframe):
	# Check that they have a valid character
	chars = Character.objects.filter(user=request.user)
	if not chars:
		return "You do not have a character defined."
	if not chars[0].corporation:
		return "Your character doesn't seem to be in a corporation."
	
	days = DAYS[timeframe]
	corporation = chars[0].corporation
	data = { 'corporation': corporation, 'timeframe': timeframe }
	now = datetime.datetime.now()
	
	# Get a QuerySet of transactions for those days
	delta = now - datetime.timedelta(days)
	transactions = Transaction.objects.filter(date__gt=delta)
	
	# Get distinct item ids
	item_ids = transactions.values_list('item').distinct()
	if not item_ids:
		return rdi_error("There are no transactions or something, idk.")
	print item_ids
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
			buy_average=Avg('price'),
			buy_maximum=Max('price'),
			buy_total=Sum('total_price'),
		))
		
		# Sell data, urgh
		item_data.update(t_sell.aggregate(
			sell_quantity=Sum('quantity'),
			sell_minimum=Min('price'),
			sell_average=Avg('price'),
			sell_maximum=Max('price'),
			sell_total=Sum('total_price'),
		))
		
		# Why are Avg results returned as floats with Decimal inputs? Who knows. Let us fix that.
		item_data['buy_average'] = Decimal('%.2f' % (item_data['buy_average']))
		item_data['sell_average'] = Decimal('%.2f' % (item_data['sell_average']))
		# Average profit
		item_data['average_profit'] = item_data['sell_average'] - item_data['buy_average']
		item_data['average_profit_per'] = Decimal('%.1f' % (item_data['average_profit'] / item_data['buy_average'] * 100))
		# Balance
		item_data['balance'] = item_data['sell_total'] - item_data['buy_total']
		item_data['class'] = rdi_balance_class(item_data['balance'])
		
		data['items'].append(item_data)
	
	# Ugh turn it into a sorted by balance list
	data['items'].sort(key=lambda a: a['balance'])
	data['items'].reverse()
	
	# GENERATE
	return render_to_response('rdi/finances_timeframe.html', data)


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
		return "You do not have a character defined."
	if not chars[0].corporation:
		return "Your character doesn't seem to be in a corporation."
	
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


def rdi_error(error_msg):
	return render_to_response('rdi/error.html', { 'error': error_msg })

def rdi_balance_class(balance):
	if balance > 0:
		return ' class="g"'
	elif balance < 0:
		return ' class="r"'
	else:
		return ''
