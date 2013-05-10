import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, InvalidPage, PageNotAnInteger

from thing.models import *
from thing.stuff import *

# ---------------------------------------------------------------------------

MONTHS = (None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

FILTER_EXPECTED = {
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
    'client': {
        'label': 'Client',
        'comps': ['eq', 'ne', 'in'],
    },
    'date': {
        'label': 'Date',
        'comps': ['eq', 'bt'],
    },
    'item': {
        'label': 'Item',
        'comps': ['eq', 'ne', 'in'],
    },
    'total': {
        'label': 'Total Amount',
        'comps': ['eq', 'ne', 'gt', 'gte', 'lt', 'lte'],
        'number': True,
    },
}

# ---------------------------------------------------------------------------
# Transaction list
@login_required
def transactions(request):
    tt = TimerThing('transactions')

    # Get profile
    profile = request.user.get_profile()

    characters = Character.objects.filter(apikeys__user=request.user.id)
    character_ids = [c.id for c in characters]

    corporations = Corporation.objects.filter(pk__in=APIKey.objects.filter(user=request.user).exclude(corp_character=None).values('corp_character__corporation'))
    corporation_ids = [c.id for c in corporations]
    
    tt.add_time('init')

    # Get a QuerySet of transactions by this user
    transaction_ids = Transaction.objects.filter(
        (
            Q(character__in=character_ids)
            &
            Q(corp_wallet__isnull=True)
        )
        |
        Q(corp_wallet__corporation__in=corporation_ids)
    )
    transaction_ids = transaction_ids.order_by('-date')

    # Get a QuerySet of transactions IDs by this user
    #characters = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))
    #transaction_ids = Transaction.objects.filter(character_id__in=characters)
    #transaction_ids = transaction_ids.order_by('-date')

    # Get only the ids, at this point joining the rest is unnecessary
    transaction_ids = transaction_ids.values_list('pk', flat=True)

    tt.add_time('transaction ids')

    # Parse and apply filters
    filters = parse_filters(request, FILTER_EXPECTED)

    if 'char' in filters:
        qs = []
        for fc, fv in filters['char']:
            if fc == 'eq':
                qs.append(Q(character=fv))
            elif fc == 'ne':
                qs.append(~Q(character=fv))
        transaction_ids = transaction_ids.filter(reduce(q_reduce_or, qs))

    if 'corp' in filters:
        qs = []
        for fc, fv in filters['corp']:
            if fc == 'eq':
                qs.append(Q(corp_wallet__corporation=fv))
            elif fc == 'ne':
                qs.append(~Q(corp_wallet__corporation=fv))
        transaction_ids = transaction_ids.filter(reduce(q_reduce_or, qs))

    # Client is a special case that requires some extra queries
    if 'client' in filters:
        qs = []
        for fc, fv in filters['client']:
            if fc == 'eq':
                qs.append(Q(name=fv))
            elif fc == 'ne':
                qs.append(~Q(name=fv))
            elif fc == 'in':
                qs.append(Q(name__icontains=fv))

        qs_reduced = reduce(q_reduce_or, qs)

        char_ids = list(Character.objects.filter(qs_reduced).values_list('id', flat=True))
        corp_ids = list(Corporation.objects.filter(qs_reduced).values_list('id', flat=True))

        transaction_ids = transaction_ids.filter(
            Q(other_char_id__in=char_ids)
            |
            Q(other_corp_id__in=corp_ids)
        )

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
        transaction_ids = transaction_ids.filter(reduce(q_reduce_or, qs))

    if 'item' in filters:
        qs = []
        for fc, fv in filters['item']:
            if fc == 'eq':
                qs.append(Q(item__name=fv))
            elif fc == 'ne':
                qs.append(~Q(item__name=fv))
            elif fc == 'in':
                qs.append(Q(item__name__icontains=fv))
        transaction_ids = transaction_ids.filter(reduce(q_reduce_or, qs))

    if 'total' in filters:
        qs = []
        for fc, fv in filters['total']:
            if fc == 'eq':
                if fv < 0:
                    qs.append(Q(buy_transction=True, total_price=abs(fv)))
                else:
                    qs.append(Q(buy_transction=False, total_price=fv))

            elif fc == 'ne':
                qs.append(~Q(total_price=fv))

            elif fc == 'gt':
                if fv > 0:
                    qs.append(Q(buy_transaction=False, total_price__gt=fv))
                else:
                    qs.append(
                        Q(buy_transaction=False, total_price__gt=abs(fv))
                        |
                        Q(buy_transaction=True, total_price__lt=abs(fv))
                    )

            elif fc == 'gte':
                if fv >= 0:
                    qs.append(Q(buy_transaction=False, total_price__gte=fv))
                else:
                    qs.append(
                        Q(buy_transaction=False, total_price__gte=abs(fv))
                        |
                        Q(buy_transaction=True, total_price__lte=abs(fv))
                    )

            elif fc == 'lt':
                if fv > 0:
                    qs.append(
                        Q(buy_transaction=False, total_price__lt=fv)
                        |
                        Q(buy_transaction=True, total_price__gt=0)
                    )
                else:
                    qs.append(Q(buy_transaction=True, total_price__gt=abs(fv)))

            elif fc == 'lte':
                if fv >= 0:
                    qs.append(
                        Q(buy_transaction=False, total_price__lte=fv)
                        |
                        Q(buy_transaction=True, total_price__gte=0)
                    )
                else:
                    qs.append(Q(buy_transaction=True, total_price__gte=abs(fv)))

        transaction_ids = transaction_ids.filter(reduce(q_reduce_or, qs))

    tt.add_time('filters')

    # Create a new paginator
    paginator = Paginator(transaction_ids, profile.entries_per_page)

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

    tt.add_time('paginator')

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

    # Build the transaction queryset now to avoid nasty subqueries
    transactions = Transaction.objects.filter(pk__in=paginated)
    transactions = transactions.select_related('corp_wallet__corporation', 'item', 'station', 'character', 'other_char', 'other_corp')
    transactions = transactions.order_by('-date')
    transactions = list(transactions)

    tt.add_time('transactions')

    # Build filter links, urgh
    for transaction in transactions:
        transaction.z_client_filter = build_filter(filters, 'client', 'eq', transaction.other_char or transaction.other_corp)
        transaction.z_item_filter = build_filter(filters, 'item', 'eq', transaction.item.name)

    tt.add_time('build links')

    # Ready template things
    json_expected = json.dumps(FILTER_EXPECTED)
    values = {
        'chars': characters,
        'corps': corporations,
    }

    tt.add_time('template bits')

    # Render template
    out = render_page(
        'thing/transactions.html',
        {
            'transactions': transactions,
            'show_item_icons': request.user.get_profile().show_item_icons,
            'paginated': paginated,
            'next': next,
            'prev': prev,
            'filters': filters,
            'json_expected': json_expected,
            'values': values,
        },
        request,
        character_ids,
        corporation_ids,
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

# ---------------------------------------------------------------------------
