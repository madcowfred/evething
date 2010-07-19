# Create your views here.
from django.shortcuts import render_to_response, get_object_or_404
from everdi.blueprints.models import BlueprintComponent, BlueprintInstance


def index(request):
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
		'blueprints/index.html',
		{
			'bpis': bpis,
			'runs': runs,
		}
	)

def details(request, bpi_id):
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
		'blueprints/details.html',
		{
			'blueprint_name': bpi.blueprint.name,
			'components': comps,
			'buy_total': buy_total,
			'sell_total': sell_total,
		}
	)
