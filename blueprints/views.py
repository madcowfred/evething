# Create your views here.
from django.shortcuts import render_to_response
from everdi.blueprints.models import BlueprintInstance

def index(request):
	bpis = BlueprintInstance.objects.all()
	
	# Spit out the response
	return render_to_response('blueprints/index.html', {
		'blueprint_instances': bpis
	})
