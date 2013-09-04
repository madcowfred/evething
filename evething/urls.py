from django.conf import settings
from django.conf.urls import patterns, include, url
from django.contrib.auth.views import login, logout
from django.http import HttpResponseRedirect


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
    (r'^account/apikey/add/$', 'account_apikey_add'),
    (r'^account/apikey/delete/$', 'account_apikey_delete'),
    (r'^account/apikey/edit/$', 'account_apikey_edit'),
    (r'^account/apikey/purge/$', 'account_apikey_purge'),
    
    (r'^skillplan/$', 'skillplan'),
    (r'^skillplan/ajax/add/skill$','skillplan_ajax_add_skill'),
    (r'^skillplan/ajax/add/remap$','skillplan_ajax_add_remap'),
    (r'^skillplan/ajax/entries/reorder/$','skillplan_ajax_reorder_entry'),
    (r'^skillplan/ajax/entries/(?P<skillplan_id>\d+)/(?P<character_id>\d+)/(?P<implants>\d+)/(?P<show_trained>\d+)/$','skillplan_ajax_render_entries_edit'),
    (r'^skillplan/create/$', 'skillplan_create'),
    (r'^skillplan/delete/$', 'skillplan_delete'),
    (r'^skillplan/edit/(?P<skillplan_id>\d+)$', 'skillplan_edit'),
    (r'^skillplan/edit/$', lambda x: HttpResponseRedirect('/skillplan/')),
    (r'^skillplan/import/$', 'skillplan_import_emp'),
    (r'^skillplan/info/edit/$', 'skillplan_edit_info'),


    (r'^assets/$', 'assets_summary'),
    (r'^assets/filter/$', 'assets_filter'),

    url(r'^blueprints/$', 'blueprints', name='blueprints'),
    (r'^blueprints/add/$', 'blueprints_add'),
    (r'^blueprints/del/$', 'blueprints_del'),
    (r'^blueprints/edit/$', 'blueprints_edit'),
    (r'^blueprints/export/$', 'blueprints_export'),
    (r'^blueprints/import/$', 'blueprints_import'),

    (r'^bpcalc/$', 'bpcalc'),

    (r'^character/(?P<character_name>[\w\'\- ]+)/$', 'character_sheet'),
    (r'^character/(?P<character_name>[\w\'\- ]+)/settings/', 'character_settings'),
    (r'^character/(?P<character_name>[\w\'\- ]+)/skillplan/(?P<skillplan_id>\d+)$', 'character_skillplan'),
    (r'^character_anon/(?P<anon_key>[a-z0-9]+)/$', 'character_anonymous',),
    (r'^character_anon/(?P<anon_key>[a-z0-9]+)/skillplan/(?P<skillplan_id>\d+)$', 'character_anonymous_skillplan'),

    (r'^contracts/', 'contracts'),

    (r'^events/$', 'events'),

    (r'^industry/$', 'industry'),

    (r'^mail/$', 'mail'),
    (r'^mail/json/body/(?P<message_id>\d+)/$', 'mail_json_body'),
    (r'^mail/json/headers/$', 'mail_json_headers'),
    (r'^mail/mark_read/$', 'mail_mark_read'),

    (r'^orders/$', 'orders'),

    (r'^trade/$', 'trade'),
    (r'^trade/(?P<year>\d{4})-(?P<month>\d{2})/$', 'trade_timeframe'),
    (r'^trade/(?P<period>all)/$', 'trade_timeframe'),
    (r'^trade/(?P<slug>[-\w]+)/$', 'trade_timeframe'),

    (r'^transactions/$', 'transactions'),

    (r'^wallet_journal/$', 'wallet_journal'),
    (r'^wallet_journal/aggregate/$', 'wallet_journal_aggregate'),
)

if getattr(settings, 'ENABLE_GSFAPI', None):
    urlpatterns += patterns('', (r'^gsfapi/', include('gsfapi.urls')))
