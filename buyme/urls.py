from django.conf.urls.defaults import *

urlpatterns = patterns('everdi.buyme.views',
	(r'^$',			'form'),
	(r'^calc/$',	'calc'),
)
