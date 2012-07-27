from django.conf import settings
#from django.conf.urls.defaults import *
from coffin.conf.urls.defaults import *
from django.contrib.auth.views import login, logout


# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Admin
    (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/', include(admin.site.urls)),
    
    # Authentication things
    url(r'^accounts/login/$', 'django.contrib.auth.views.login', name="auth_login"),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}, name="auth_logout"),
)

urlpatterns += patterns('thing.views',
    url(r'^$', 'home', name='home'),

    (r'^account/$', 'account'),
    (r'^account/change_password/$', 'account_change_password'),
    (r'^account/settings/$', 'account_settings'),
    (r'^account/skillplan_add/$', 'account_skillplan_add'),

    url(r'^apikeys/$', 'apikeys', name='apikeys'),
    (r'^apikeys/add/$', 'apikeys_add'),
    (r'^apikeys/delete/$', 'apikeys_delete'),
    (r'^apikeys/edit/$', 'apikeys_edit'),

    (r'^assets/$', 'assets'),

    url(r'^blueprints/$', 'blueprints', name='blueprints'),
    (r'^blueprints/add/$', 'blueprints_add'),
    (r'^blueprints/del/$', 'blueprints_del'),
    (r'^blueprints/edit/$', 'blueprints_edit'),

    (r'^bpcalc/$', 'bpcalc'),
    
    url(r'^character/(?P<character_name>[\w\'\- ]+)/$', 'character', name='character'),
    (r'^character/(?P<character_name>[\w\'\- ]+)/settings/', 'character_settings'),
    (r'^character/(?P<character_name>[\w\'\- ]+)/skillplan/(?P<skillplan_id>\d+)$', 'character_skillplan'),
    url(r'^character_anon/(?P<anon_key>[a-z0-9]+)/$', 'character_anonymous', name='character_anonymous'),
    
    (r'^events/$', 'events'),
    
    (r'^orders/$', 'orders'),
    
    (r'^market_scan/$', 'market_scan'),

    (r'^trade/$', 'trade'),
    (r'^trade/(?P<year>\d{4})-(?P<month>\d{2})/$', 'trade_timeframe'),
    (r'^trade/(?P<period>all)/$', 'trade_timeframe'),
    (r'^trade/(?P<slug>[-\w]+)/$', 'trade_timeframe'),
    
    (r'^transactions/$', 'transactions'),
    (r'^transactions/(?P<item_id>all|\d+)/(?P<year>\d{4})-(?P<month>\d{2})/$', 'transactions_item'),
    url(r'^transactions/(?P<item_id>all|\d+)/(?P<period>all)/$', 'transactions_item', name='transactions-all'),
    (r'^transactions/(?P<item_id>all|\d+)/(?P<slug>[-\w]+)/$', 'transactions_item'),
)

# Redirects
urlpatterns += patterns('django.views.generic.simple',
    ('^transactions/(?P<item_id>all|\d+)/$', 'redirect_to', { 'url': '/transactions/%(item_id)s/all/', 'permanent': False }),
)

# If we're running under DEBUG, serve static media files
#if settings.DEBUG:
#    urlpatterns += patterns('',
#        (r'^raidthing_media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
#    )
