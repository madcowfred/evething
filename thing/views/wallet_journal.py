# ------------------------------------------------------------------------------
# Copyright (c) 2010-2013, EVEthing team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     Redistributions of source code must retain the above copyright notice, this
#       list of conditions and the following disclaimer.
#     Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
# ------------------------------------------------------------------------------

import json

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

#from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, InvalidPage, PageNotAnInteger
from django.db import connection
from django.db.models import Q, Avg, Count, Max, Min, Sum

from thing.models import *
from thing.stuff import *
from thing.views.trade import _month_range

# ---------------------------------------------------------------------------

JOURNAL_EXPECTED = {
    'char': {
        'label': 'Character',
        'comps': ['eq', 'ne', 'in'],
        'number': True,
    },
    'corp': {
        'label': 'Corporation',
        'comps': ['eq', 'ne', 'in'],
        'number': True,
    },
    'amount': {
        'label': 'Amount',
        'comps': ['eq', 'ne', 'gt', 'gte', 'lt', 'lte'],
        'number': True,
    },
    'date': {
        'label': 'Date',
        'comps': ['eq', 'bt'],
    },
    'owners': {
        'label': 'Owners',
        'comps': ['eq', 'ne', 'in'],
    },
    'reftype': {
        'label': 'Ref Type',
        'comps': ['eq', 'ne', 'in'],
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

    # Parse filters and apply magic
    filters, journal_ids, days = _journal_queryset(request, character_ids, corporation_ids)

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
                if ':' in thing:
                    item_ids.add(int(thing.split(':')[0]))

    char_map = Character.objects.in_bulk(owner_ids)
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
            entry.z_description = '"%s"' % (entry.get_unescaped_reason()[5:].strip())
        # Insurance, arg_name is the item_id of the ship that exploded
        elif entry.ref_type_id == 19:
            if entry.amount >= 0:
                item = item_map.get(int(entry.arg_name))
                if item:
                    entry.z_description = 'Insurance payment for loss of a %s' % (item.name)
            else:
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
                if ':' in thing:
                    item_id, count = thing.split(':')
                    item = item_map.get(int(item_id))
                    if item:
                        killed.append((item.name, '%sx %s' % (count, item.name)))
                elif thing == '...':
                    killed.append(('ZZZ', '... (list truncated)'))

            # Sort killed
            killed = [k[1] for k in sorted(killed)]

            entry.z_description = 'Bounty prizes for killing pirates in %s' % (entry.arg_name.strip())
            entry.z_hover = '||'.join(killed)

        # Filter links
        entry.z_reftype_filter = build_filter(filters, 'reftype', 'eq', entry.ref_type_id)
        entry.z_owner1_filter = build_filter(filters, 'owners', 'eq', entry.z_owner1_char or entry.z_owner1_corp or entry.z_owner1_alliance)
        entry.z_owner2_filter = build_filter(filters, 'owners', 'eq', entry.z_owner2_char or entry.z_owner2_corp or entry.z_owner2_alliance)

    # Render template
    return render_page(
        'thing/wallet_journal.html',
        {
            'json_data': _json_data(characters, corporations, filters),
            'total_amount': total_amount,
            'days': days,
            'entries': entries,
            'paginated': paginated,
            'next': next,
            'prev': prev,
            'ignoreself': 'ignoreself' in request.GET,
            'group_by': {},
        },
        request,
        character_ids,
        corporation_ids,
    )

# ---------------------------------------------------------------------------

@login_required
def wallet_journal_aggregate(request):
    characters = Character.objects.filter(apikeys__user=request.user.id)
    character_ids = [c.id for c in characters]

    corporations = Corporation.objects.filter(pk__in=APIKey.objects.filter(user=request.user).exclude(corp_character=None).values('corp_character__corporation'))
    corporation_ids = [c.id for c in corporations]

    # Parse filters and apply magic
    filters, journal_ids, days = _journal_queryset(request, character_ids, corporation_ids)

    # Group by
    group_by = {
        'date': request.GET.get('group_by_date', 'year'),
        'owner1': request.GET.get('group_by_owner1'),
        'owner2': request.GET.get('group_by_owner2'),
        'reftype': request.GET.get('group_by_reftype'),
        'source': request.GET.get('group_by_source'),
    }

    # Build a horrifying ORM query
    if group_by['date'] == 'day':
        extras = {
            'year': 'EXTRACT(year FROM date)',
            'month': 'EXTRACT(month FROM date)',
            'day': 'EXTRACT(day FROM date)',
        }
        values = ['year', 'month', 'day']

    elif group_by['date'] == 'month':
        extras = {
            'year': 'EXTRACT(year FROM date)',
            'month': 'EXTRACT(month FROM date)',
        }
        values = ['year', 'month']

    else:
        group_by_date = 'year'
        extras = {
            'year': 'EXTRACT(year FROM date)',
        }
        values = ['year']

    empty_colspan = 3
    for k, v in group_by.items():
        if v:
            empty_colspan += 1

    if group_by['owner1']:
        values.append('owner1_id')
    if group_by['owner2']:
        values.append('owner2_id')
    if group_by['reftype']:
        values.append('ref_type')
    if group_by['source']:
        values.append('character')
        values.append('corp_wallet')

    journal_ids = journal_ids.extra(
        select=extras,
    ).values(
        *values
    ).annotate(
        entries=Count('id'),
        total_amount=Sum('amount'),
    ).order_by(
    #    *orders
    )

    # Aggregate!
    wja = WJAggregator(group_by)

    for entry in journal_ids:
        print entry
        wja.add_entry(entry)

    wja.finalise()

    # Render template
    return render_page(
        'thing/wallet_journal_aggregate.html',
        {
            'json_data': _json_data(characters, corporations, filters),
            'agg_data': wja.data,
            'group_by': group_by,
            'empty_colspan': empty_colspan,
        },
        request,
    )

# ---------------------------------------------------------------------------

class WJAggregator(object):
    def __init__(self, group_by):
        self.__entries = []
        self.data = []

        self.__characters = set()
        self.__corp_wallets = set()
        self.__owners = set()
        self.__reftypes = set()

        self.__group_by = group_by

    def add_entry(self, entry):
        if self.__group_by['source']:
            self.__characters.add(entry['character'])
            self.__corp_wallets.add(entry['corp_wallet'])

        if self.__group_by['reftype']:
            self.__reftypes.add(entry['ref_type'])

        if self.__group_by['owner1']:
            self.__owners.add(entry['owner1_id'])
        if self.__group_by['owner2']:
            self.__owners.add(entry['owner2_id'])

        self.__entries.append(entry)

    def __cmp_func(self, a, b):
        # date, groupby tuple, entry
        c = cmp(a[0], b[0])
        if c != 0:
            return c * -1

        c = cmp(a[1], b[1])
        if c != 0:
            return c * -1

        return cmp(a[2], b[2])

    def finalise(self):
        ref_map = RefType.objects.in_bulk(self.__reftypes)
        char_map = Character.objects.in_bulk(self.__owners | self.__characters)
        corp_map = Corporation.objects.in_bulk(self.__owners)
        alliance_map = Alliance.objects.in_bulk(self.__owners)
        wallet_map = CorpWallet.objects.select_related('corporation').in_bulk(self.__corp_wallets)

        # Build a horrifying sorted entries list I gues
        for entry in self.__entries:
            if 'day' in entry:
                date = '%04d-%02d-%02d' % (entry['year'], int(entry['month']), int(entry['day']))
            elif 'month' in entry:
                date = '%04d-%02d' % (int(entry['year']), int(entry['month']))
            else:
                date = '%04d' % (int(entry['year']))

            group_data = []

            if self.__group_by['source']:
                cw = wallet_map.get(entry['corp_wallet'])
                if cw is not None:
                    group_data.extend([cw.corporation.name, cw])
                else:
                    char = char_map.get(entry['character'])
                    if char is not None:
                        group_data.extend([char.name, char])
                    else:
                        group_data.extend([None, 'Unknown ID: %s' % (entry['character'])])

            if self.__group_by['reftype']:
                ref_name = ref_map[entry['ref_type']].name
                group_data.extend([ref_name, ref_name])

            if self.__group_by['owner1']:
                owner1_id = entry['owner1_id']
                owner1 = char_map.get(owner1_id, corp_map.get(owner1_id, alliance_map.get(owner1_id)))
                if owner1 is not None:
                    group_data.extend([owner1.name, owner1])
                else:
                    group_data.extend([None, 'Unknown ID: %s' % (owner1_id)])

            if self.__group_by['owner2']:
                owner2_id = entry['owner2_id']
                owner2 = char_map.get(owner2_id, corp_map.get(owner2_id, alliance_map.get(owner2_id)))
                if owner2 is not None:
                    group_data.extend([owner2.name, owner2])
                else:
                    group_data.extend([None, 'Unknown ID: %s' % (owner2_id)])

            self.data.append((
                date,
                entry['total_amount'],
                group_data,
                entry,
            ))

        self.data.sort(cmp=self.__cmp_func)

# ---------------------------------------------------------------------------

def _journal_queryset(request, character_ids, corporation_ids):
    journal_ids = JournalEntry.objects.filter(
        (
            Q(character__in=character_ids)
            &
            Q(corp_wallet__isnull=True)
        )
        |
        Q(corp_wallet__corporation__in=corporation_ids)
    )

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
                if fv == -1:
                    qs.append(Q(corp_wallet__corporation__isnull=False))
                else:
                    qs.append(Q(corp_wallet__corporation=fv))
            elif fc == 'ne':
                if fv == -1:
                    qs.append(Q(corp_wallet__corporation__isnull=True))
                else:
                    qs.append(~Q(corp_wallet__corporation=fv))
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

    if 'date' in filters:
        qs = []
        for fc, fv in filters['date']:
            if fc == 'eq':
                try:
                    start = datetime.datetime.strptime(fv, '%Y-%m-%d')
                    end = datetime.datetime.strptime('%s 23:59:59' % (fv), '%Y-%m-%d %H:%M:%S')
                    qs.append(Q(date__range=(start, end)))
                except ValueError:
                    pass
            elif fc == 'bt':
                parts = fv.split(',')
                if len(parts) == 2:
                    try:
                        start = datetime.datetime.strptime(parts[0], '%Y-%m-%d')
                        end = datetime.datetime.strptime('%s 23:59:59' % (parts[1]), '%Y-%m-%d %H:%M:%S')
                        if start < end:
                            qs.append(Q(date__range=(start, end)))
                    except ValueError:
                        pass
        if qs:
            journal_ids = journal_ids.filter(reduce(q_reduce_or, qs))

    # Owners is a special case that requires some extra queries
    if 'owners' in filters:
        qs = []
        for fc, fv in filters['owners']:
            if fc == 'eq':
                qs.append(Q(name=fv))
            elif fc == 'ne':
                qs.append(~Q(name=fv))
            elif fc == 'in':
                qs.append(Q(name__icontains=fv))

        qs_reduced = reduce(q_reduce_or, qs)

        o_chars = Character.objects.filter(qs_reduced)
        o_corps = Corporation.objects.filter(qs_reduced)
        o_alliances = Alliance.objects.filter(qs_reduced)

        owner_ids = set()
        for char in o_chars:
            owner_ids.add(char.id)
        for corp in o_corps:
            owner_ids.add(corp.id)
        for alliance in o_alliances:
            owner_ids.add(alliance.id)

        journal_ids = journal_ids.filter(
            Q(owner1_id__in=owner_ids)
            |
            Q(owner2_id__in=owner_ids)
        )

    if 'reftype' in filters:
        qs = []
        for fc, fv in filters['reftype']:
            if fc == 'eq':
                qs.append(Q(ref_type=fv))
            elif fc == 'ne':
                qs.append(~Q(ref_type=fv))
        journal_ids = journal_ids.filter(reduce(q_reduce_or, qs))

    # Apply days limit
    try:
        days = int(request.GET.get('days', '0'))
    except ValueError:
        days = 0
    else:
        days = max(0, min(days, 9999))

    if days > 0:
        limit = datetime.datetime.utcnow() - datetime.timedelta(days)
        journal_ids = journal_ids.filter(date__gte=limit)

    # Apply ignoreself
    if 'ignoreself' in request.GET:
        journal_ids = journal_ids.filter(
            ~(
                Q(owner1_id__in=character_ids)
                &
                Q(owner2_id__in=character_ids)
            )
        )

    return filters, journal_ids, days

# ---------------------------------------------------------------------------

def _json_data(characters, corporations, filters):
    data = dict(
        expected=JOURNAL_EXPECTED,
        filters=filters,
        values=dict(
            char={},
            corp={},
            reftype={},
        ),
    )

    for char in characters:
        data['values']['char'][char.id] = char.name.replace("'", '&apos;')
    for corp in corporations:
        data['values']['corp'][corp.id] = corp.name.replace("'", '&apos;')
    for reftype in RefType.objects.exclude(name='').exclude(id__gte=1000):
        data['values']['reftype'][reftype.id] = reftype.name

    return json.dumps(data)

# ---------------------------------------------------------------------------
