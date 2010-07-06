from django.conf.urls.defaults import *
from everdi.blueprints.models import BlueprintInstance

info_dict = {
	'queryset': BlueprintInstance.objects.all(),
}

urlpatterns = patterns('',
    (r'^$', 'django.views.generic.list_detail.object_list', info_dict),
    (r'^(?P<object_id>\d+)/$', 'django.views.generic.list_detail.object_detail', info_dict),
)


#from django.conf.urls.defaults import *
#
#urlpatterns = patterns('everdi.blueprints.views',
#	(r'^$', 'index'),
#)
