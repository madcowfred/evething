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
			'production_time': bpi.nice_production_time(runs=runs),
			'unit_cost_buy': bpi.nice_production_cost(runs=runs),
			'unit_cost_sell': bpi.nice_production_cost(runs=runs, use_sell=True),
			'market_price': bpi.blueprint.item.nice_sell_median(),
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
def corp_index(request):
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
		
		balance = sell_total - buy_total
		data['%sday_balance' % days] = balance
		if balance > 0:
			data['%sday_class' % days] = ' class="g"'
		elif balance < 0:
			data['%sday_class' % days] = ' class="r"'
		else:
			data['%sday_class' % days] = ''
	
	
	return render_to_response('rdi/corp_index.html', data)


def rdi_error(error_msg):
	return render_to_response('rdi/error.html', { 'error': error_msg })
