from django.conf.urls.defaults import *
from django.contrib.auth.views import login, logout


# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
	(r'^blueprints/$',        'everdi.rdi.views.blueprints'),
	(r'^corp/$',              'everdi.rdi.views.corp_index'),
	(r'^corp/(?P<days>\d+)/$', 'everdi.rdi.views.corp_details'),
	(r'^corp/(?P<days>\d+)/(?P<item_id>\d+)/$', 'everdi.rdi.views.corp_item'),
	#(r'^buyme/',       include('everdi.buyme.urls')),
	
	# Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
	# to INSTALLED_APPS to enable admin documentation:
	(r'^admin/doc/', include('django.contrib.admindocs.urls')),
	
	# Uncomment the next line to enable the admin:
	(r'^admin/', include(admin.site.urls)),
	
	# Login/logout crap
	(r'^accounts/login/$',  login),
	(r'^accounts/logout/$', logout),
)
