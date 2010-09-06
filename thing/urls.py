from django.conf.urls.defaults import *

urlpatterns = patterns('everdi.blueprints.views',
    (r'^$',					'index'),
    (r'^(?P<bpi_id>\d+)/$', 'details'),
)
