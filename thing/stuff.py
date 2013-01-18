import datetime
import gzip
import time
from cStringIO import StringIO
from urllib import urlencode

try:
    import xml.etree.cElementTree as ET
except:
    import xml.etree.ElementTree as ET

#from django.conf import settings
from django.db.models import Count, Q
from django.template import RequestContext

from coffin.shortcuts import render_to_response

# ---------------------------------------------------------------------------
# Wrapper around render_to_response
def render_page(template, data, request, character_ids=None, corporation_ids=None):
    from thing.models import Character, Corporation, Contract, APIKey, IndustryJob

    utcnow = datetime.datetime.utcnow()
    
    if request.user.is_authenticated():
        if character_ids is None:
            character_ids = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))

        if corporation_ids is None:
            #corporation_ids = list(Corporation.objects.filter(pk__in=APIKey.objects.filter(user=request.user).exclude(corp_character=None).values('corp_character__corporation')).values_list('id', flat=True))
            corporation_ids = list(APIKey.objects.filter(user=request.user).exclude(corp_character=None).values_list('corp_character__corporation', flat=True))

        # Aggregate outstanding contracts
        contracts = Contract.objects.filter(
            Q(assignee_id__in=character_ids)
            |
            Q(assignee_id__in=corporation_ids)
        )
        contracts = contracts.filter(status='Outstanding')
        data['nav_contracts'] = contracts.aggregate(t=Count('id'))['t']

        # Aggregate ready industry jobs
        jobs = IndustryJob.objects.filter(
            Q(character__in=character_ids, corporation=None)
            |
            Q(corporation__in=corporation_ids)
        )
        jobs = jobs.filter(completed=False, end_time__lte=utcnow)
        data['nav_industryjobs'] = jobs.aggregate(t=Count('id'))['t']

    return render_to_response(template, data, RequestContext(request))

# ---------------------------------------------------------------------------
# Times things
class TimerThing:
    def __init__(self, name):
        self.times = []
        self.add_time(name)

    def add_time(self, name):
        self.times.append([time.time(), name])

    def finished(self):
        print 'TimerThing: %s' % (self.times[0][1])
        print '-' * 23
        for i in range(1, len(self.times)):
            t, name = self.times[i]
            print '%-15s: %.3fs' % (name, t - self.times[i-1][0])
        print '-' * 23
        print '%-15s: %.3fs' % ('total', self.times[-1][0] - self.times[0][0])

# ---------------------------------------------------------------------------
# Fetch all rows from a cursor as a list of dictionaries
def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

# ---------------------------------------------------------------------------
# Convert a datetime.timedelta object into a number of seconds
def total_seconds(delta):
    return (delta.days * 24 * 60 * 60) + delta.seconds

# ---------------------------------------------------------------------------

def build_filter(filters, filter_type, filter_comp, filter_value):
    params = []

    for ft, stuff in filters.items():
        if ft == filter_type:
            continue

        for fc, fv in stuff:
            params.append(('ft', ft))
            params.append(('fc', fc))
            params.append(('fv', fv))

    params.append(('ft', filter_type))
    params.append(('fc', filter_comp))
    params.append(('fv', filter_value))

    return urlencode(params)

# ---------------------------------------------------------------------------
# Parse filter GET variables
def parse_filters(request, expected):
    # retrieve any supplied filter values
    f_types = request.GET.getlist('ft')
    f_comps = request.GET.getlist('fc')
    f_values = request.GET.getlist('fv')

    # run.
    filters = {}

    min_len = min(len(f_types), len(f_comps), len(f_values))
    for ft, fc, fv in zip(f_types[:min_len], f_comps[:min_len], f_values[:min_len]):
        ex = expected.get(ft)
        if ex is None:
            continue

        # If the entry must be a number, verify that
        if ex.get('number', False):
            try:
                fv = int(fv)
            except ValueError:
                continue

        # Make sure the comparison is valid
        if fc not in ex.get('comps', []):
            continue

        # Keep it
        filters.setdefault(ft, []).append([fc, fv])

    return filters

# ---------------------------------------------------------------------------

def q_reduce_or(a, b):
    return a | b

def q_reduce_and(a, b):
    return a & b

# ---------------------------------------------------------------------------
