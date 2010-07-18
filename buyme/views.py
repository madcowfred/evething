# Create your views here.
from django.shortcuts import render_to_response

from everdi.blueprints.models import BlueprintComponent, BlueprintInstance, Item
from everdi.buyme.price_override import PRICE_OVERRIDE
from everdi.common import commas


def form(request):
	# This is a horrible abomination. I am sorry.
	item_map = {}
	for bpi in BlueprintInstance.objects.all():
		for item in bpi.blueprint.components.all():
			item_map[item.id] = item.name
	
	item_list = [(k, v) for k, v in item_map.items()]
	item_list.sort()
	
	return render_to_response(
		'buyme/form.html',
		{ 'items': item_list },
	)

def calc(request):
	rows = []
	total = 0
	
	for k, v in request.GET.items():
		if k.isdigit() and v.isdigit():
			results = Item.objects.filter(id=k)
			if not results:
				continue
			
			price = PRICE_OVERRIDE.get(int(k), 0) or results[0].buy_median
			
			unit_total = price * int(v)
			total += unit_total
			
			rows.append({
				'name': results[0].name,
				'count': v,
				'per_unit': commas(price),
				'total': commas(unit_total),
			})
	
	return render_to_response(
		'buyme/results.html',
		{
			'rows': rows,
			'total': commas(total),
		}
	)
