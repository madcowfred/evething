from django.conf import settings
from django.conf.urls.defaults import *
from django.contrib.auth.views import login, logout


# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
	# Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
	# to INSTALLED_APPS to enable admin documentation:
	(r'^admin/doc/', include('django.contrib.admindocs.urls')),
	
	# Uncomment the next line to enable the admin:
	(r'^admin/', include(admin.site.urls)),
	
	# Login/logout crap
	(r'^accounts/login/$',  login),
	(r'^accounts/logout/$', logout),
)

urlpatterns += patterns('everdi.rdi.views',
	(r'^blueprints/$', 'blueprints'),
	(r'^finances/$', 'finances'),
	(r'^finances/(?P<timeframe>day|week|month|all)/$', 'finances_timeframe'),
	(r'^orders/$', 'orders'),
	(r'^transactions/$', 'transactions'),
	(r'^transactions/(?P<timeframe>day|week|month|all)/(?P<item_id>\d+)/$', 'transactions_item'),
	#(r'^buyme/',       include('everdi.buyme.urls')),
)

if settings.DEBUG:
	urlpatterns += patterns('',
		(r'^rdi_media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
	)
