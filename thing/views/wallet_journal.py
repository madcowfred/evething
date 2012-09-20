import json

#from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, InvalidPage, PageNotAnInteger
from django.db import connection
from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.template import RequestContext

from coffin.shortcuts import *

from thing.models import *
from thing.stuff import parse_filters, q_reduce_or
from thing.views.trade import _month_range

# ---------------------------------------------------------------------------

JOURNAL_EXPECTED = {
    'char': {
        'comps': ['eq', 'ne'],
        'number': True,
    },
    'corp': {
        'comps': ['eq', 'ne'],
        'number': True,
    },
    'reftype': {
        'comps': ['eq', 'ne'],
        'number': True,
    },
    #'owners': {
    #    'comps': ['eq', 'ne', 'in'],
    #},
    'amount': {
        'comps': ['eq', 'ne', 'gt', 'gte', 'lt', 'lte'],
        'number': True,
    },
}

# ---------------------------------------------------------------------------
# Wallet journal
@login_required
def wallet_journal(request):
    # Get profile
    profile = request.user.get_profile()

    characters = Character.objects.filter(apikeys__user=request.user.id)
    character_ids = [c.id for c in characters]

    corporations = Corporation.objects.filter(pk__in=APIKey.objects.filter(user=request.user).exclude(corp_character=None).values('corp_character__corporation'))
    corporation_ids = [c.id for c in corporations]

    journal_ids = JournalEntry.objects.filter(
        (
            Q(character__in=character_ids)
            &
            Q(corp_wallet__isnull=True)
        )
        |
        Q(corp_wallet__corporation__in=corporation_ids)
    )

    # Days
    days = request.GET.get('days', '')
    if days.isdigit() and int(days) >= 0:
        days = int(days)
    else:
        days = 0

    # Parse and apply filters
    filters = parse_filters(request, JOURNAL_EXPECTED)
    if 'char' in filters:
        qs = []
        for fc, fv in filters['char']:
            if fc == 'eq':
                qs.append(Q(character=fv))
            elif fc == 'ne':
                qs.append(~Q(character=fv))
        journal_ids = journal_ids.filter(reduce(q_reduce_or, qs))

    if 'corp' in filters:
        qs = []
        for fc, fv in filters['corp']:
            if fc == 'eq':
                qs.append(Q(corp_wallet__corporation=fv))
            elif fc == 'ne':
                qs.append(~Q(corp_wallet__corporation=fv))
        journal_ids = journal_ids.filter(reduce(q_reduce_or, qs))

    if 'reftype' in filters:
        qs = []
        for fc, fv in filters['reftype']:
            if fc == 'eq':
                qs.append(Q(ref_type=fv))
            elif fc == 'ne':
                qs.append(~Q(ref_type=fv))
        journal_ids = journal_ids.filter(reduce(q_reduce_or, qs))

    if 'amount' in filters:
        qs = []
        for fc, fv in filters['amount']:
            if fc == 'eq':
                qs.append(Q(amount=fv))
            elif fc == 'ne':
                qs.append(~Q(amount=fv))
            elif fc == 'gt':
                qs.append(Q(amount__gt=fv))
            elif fc == 'gte':
                qs.append(Q(amount__gte=fv))
            elif fc == 'lt':
                qs.append(Q(amount__lt=fv))
            elif fc == 'lte':
                qs.append(Q(amount__lte=fv))
        journal_ids = journal_ids.filter(reduce(q_reduce_or, qs))

    # Apply days limit
    if days > 0:
        limit = datetime.datetime.utcnow() - datetime.timedelta(days)
        journal_ids = journal_ids.filter(date__gte=limit)

    # Calculate a total value
    total_amount = journal_ids.aggregate(t=Sum('amount'))['t']

    # Get only the ids, at this point joining the rest is unnecessary
    journal_ids = journal_ids.values_list('pk', flat=True)

    # Create a new paginator
    paginator = Paginator(journal_ids, profile.entries_per_page)

    # Make sure page request is an int, default to 1st page
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    # If page request is out of range, deliver last page of results
    try:
        paginated = paginator.page(request.GET.get('page'))
    except PageNotAnInteger:
        # Page is not an integer, use first page
        paginated = paginator.page(1)
    except EmptyPage:
        # Page is out of range, deliver last page
        paginated = paginator.page(paginator.num_pages)

    # Actually execute the query to avoid a nested subquery
    paginated_ids = list(paginated.object_list.all())
    entries = JournalEntry.objects.filter(pk__in=paginated_ids).select_related('character', 'corp_wallet__corporation')
    
    # Do page number things
    hp = paginated.has_previous()
    hn = paginated.has_next()
    prev = []
    next = []

    if hp:
        # prev and next, use 1 of each
        if hn:
            prev.append(paginated.previous_page_number())
            next.append(paginated.next_page_number())
        # no next, add up to 2 previous links
        else:
            for i in range(paginated.number - 1, 0, -1)[:2]:
                prev.append(i)
    else:
        # no prev, add up to 2 next links
        for i in range(paginated.number + 1, paginator.num_pages)[:2]:
            next.append(i)

    # Do some stuff with entries
    item_ids = set()
    owner_ids = set()
    reftype_ids = set()
    station_ids = set()

    for entry in entries:
        owner_ids.add(entry.owner1_id)
        owner_ids.add(entry.owner2_id)
        reftype_ids.add(entry.ref_type_id)

        # Insurance
        if entry.ref_type_id == 19:
            item_ids.add(int(entry.arg_name))
        # Clone Transfer
        elif entry.ref_type_id == 52:
            station_ids.add(int(entry.arg_id))
        # Bounty Prizes
        elif entry.ref_type_id == 85:
            for thing in entry.reason.split(','):
                thing = thing.strip()
                if thing:
                    item_ids.add(int(thing.split(':')[0]))

    char_map = SimpleCharacter.objects.in_bulk(owner_ids)
    corp_map = Corporation.objects.in_bulk(owner_ids)
    alliance_map = Alliance.objects.in_bulk(owner_ids)
    item_map = Item.objects.in_bulk(item_ids)
    rt_map = RefType.objects.in_bulk(reftype_ids)
    station_map = Station.objects.in_bulk(station_ids)

    for entry in entries:
        # Owner 1
        if entry.owner1_id in character_ids:
            entry.z_owner1_mine = True
        entry.z_owner1_char = char_map.get(entry.owner1_id)
        entry.z_owner1_corp = corp_map.get(entry.owner1_id)
        entry.z_owner1_alliance = alliance_map.get(entry.owner1_id)

        # Owner 2
        if entry.owner2_id in character_ids:
            entry.z_owner2_mine = True
        entry.z_owner2_char = char_map.get(entry.owner2_id)
        entry.z_owner2_corp = corp_map.get(entry.owner2_id)
        entry.z_owner2_alliance = alliance_map.get(entry.owner2_id)

        # RefType
        entry.z_reftype = rt_map.get(entry.ref_type_id)

        # Inheritance
        if entry.ref_type_id == 9:
            entry.z_description = entry.reason
        # Player Donation/Corporation Account Withdrawal
        elif entry.ref_type_id in (10, 37) and entry.reason != '':
            entry.z_description = '"%s"' % (entry.reason[5:].strip())
        # Insurance, arg_name is the item_id of the ship that exploded
        elif entry.ref_type_id == 19:
            if amount > 0:
                item = item_map.get(int(entry.arg_name))
                if item:
                    entry.z_description = 'Insurance payment for loss of a %s' % (item.name)
            elif amount < 0:
                entry.z_description = 'Insurance purchased (RefID: %s)' % (entry.arg_name[1:])
        # Clone Transfer, arg_name is the name of the station you're going to
        elif entry.ref_type_id == 52:
            station = station_map.get(entry.arg_id)
            if station:
                entry.z_description = 'Clone transfer to %s' % (station.short_name)
        # Bounty Prizes
        elif entry.ref_type_id == 85:
            killed = []

            for thing in entry.reason.split(','):
                thing = thing.strip()
                if thing:
                    item_id, count = thing.split(':')
                    item = item_map.get(int(item_id))
                    if item:
                        killed.append((item.name, '%sx %s' % (count, item.name)))

            # Sort killed
            killed = [k[1] for k in sorted(killed)]

            entry.z_description = 'Bounty prizes for killing pirates in %s' % (entry.arg_name.strip())
            entry.z_hover = '||'.join(killed)

    # Ready template things
    json_expected = json.dumps(JOURNAL_EXPECTED)
    values = {
        'chars': characters,
        'corps': corporations,
        'reftypes': RefType.objects.exclude(name='').exclude(id__gte=1000),
    }

    # Render template
    return render_to_response(
        'thing/wallet_journal.html',
        {
            'json_expected': json_expected,
            'values': values,
            'filters': filters,
            'total_amount': total_amount,
            'days': days,
            'entries': entries,
            'paginated': paginated,
            'next': next,
            'prev': prev,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------

def wjthing(request):
    character_ids = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))
    corporation_ids = list(APIKey.objects.filter(user=request.user).exclude(corp_character=None).values_list('corp_character__corporation__id', flat=True))

    summaries = JournalSummary.objects.filter(
        (
            Q(character__in=character_ids)
            &
            Q(corp_wallet__isnull=True)
        )
        |
        Q(corp_wallet__corporation__in=corporation_ids)
    )

    months = summaries.values('year','month').annotate(sum_in=Sum('total_in'), sum_out=Sum('total_out'), sum_bal=Sum('balance')).order_by('-year', '-month')

    return render_to_response(
        'thing/wjthing.html',
        {
            'months': months,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
