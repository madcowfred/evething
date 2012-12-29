import json

#from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, InvalidPage, PageNotAnInteger
#from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.template import RequestContext

from coffin.shortcuts import *

from thing.models import *
from thing.stuff import parse_filters, q_reduce_or

# ---------------------------------------------------------------------------

MONTHS = (None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

FILTER_EXPECTED = {
    'char': {
        'comps': ['eq', 'ne'],
        'number': True,
    },
    'corp': {
        'comps': ['eq', 'ne'],
        'number': True,
    },
    'client': {
        'comps': ['eq', 'ne', 'in'],
    },
    'item': {
        'comps': ['eq', 'ne', 'in'],
    },
    'amount': {
        'comps': ['eq', 'ne', 'gt', 'gte', 'lt', 'lte'],
        'number': True,
    },
}

# ---------------------------------------------------------------------------
# Transaction list
@login_required
def transactions(request):
    # Get profile
    profile = request.user.get_profile()

    characters = Character.objects.filter(apikeys__user=request.user.id)
    character_ids = [c.id for c in characters]

    corporations = Corporation.objects.filter(pk__in=APIKey.objects.filter(user=request.user).exclude(corp_character=None).values('corp_character__corporation'))
    corporation_ids = [c.id for c in corporations]
    
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

    # Parse and apply filters
    filters = parse_filters(request, FILTER_EXPECTED)

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
        transaction_ids = transaction_ids.filter(reduce(q_reduce_or, qs))

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

        char_ids = list(SimpleCharacter.objects.filter(qs_reduced).values_list('id', flat=True))
        corp_ids = list(Corporation.objects.filter(qs_reduced).values_list('id', flat=True))

        transaction_ids = transaction_ids.filter(
            Q(other_char_id__in=char_ids)
            |
            Q(other_corp_id__in=corp_ids)
        )


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

    # Actually execute the query to avoid a nested subquery
    paginated_ids = list(paginated.object_list.all())
    transactions = Transaction.objects.filter(pk__in=paginated_ids).select_related('corp_wallet__corporation', 'item', 'station', 'character', 'other_char', 'other_corp')
    transactions = transactions.order_by('-date')

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

    # Ready template things
    json_expected = json.dumps(FILTER_EXPECTED)
    values = {
        'chars': characters,
        'corps': corporations,
    }

    # Render template
    return render_to_response(
        'thing/transactions.html',
        {
            'transactions': transactions,
            'paginated': paginated,
            'next': next,
            'prev': prev,
            'filters': filters,
            'json_expected': json_expected,
            'values': values,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Transaction details for last x days for specific item
@login_required
def transactions_item(request, item_id, year=None, month=None, period=None, slug=None):
    data = {}

    characters = Character.objects.filter(apikeys__user=request.user.id)
    character_ids = [c.id for c in characters]

    corporations = Corporation.objects.filter(pk__in=APIKey.objects.filter(user=request.user).exclude(corp_character=None).values('corp_character__corporation'))
    corporation_ids = [c.id for c in corporations]
    
    # Get a QuerySet of transactions by this user
    transactions = Transaction.objects.filter(
        (
            Q(character__in=character_ids)
            &
            Q(corp_wallet__isnull=True)
        )
        |
        Q(corp_wallet__corporation__in=corporation_ids)
    )
    transactions = transactions.order_by('-date')
    #transactions = Transaction.objects.filter(character__apikeys__user=request.user).order_by('-date')
    
    # If item_id is an integer we should filter on that item_id
    if item_id.isdigit():
        transactions = transactions.filter(item=item_id)
        data['item'] = Item.objects.get(pk=item_id).name
    else:
        data['item'] = 'all items'
    
    # Year/Month
    if year and month:
        month = int(month)
        transactions = transactions.filter(date__year=year, date__month=month)
        data['timeframe'] = '%s %s' % (MONTHS[month], year)
    # Timeframe slug
    elif slug:
        camp = get_object_or_404(Campaign, slug=slug)
        transactions = camp.get_transactions_filter(transactions)
        data['timeframe'] = '%s (%s -> %s)' % (camp.title, camp.start_date, camp.end_date)
    # All
    else:
        data['timeframe'] = 'all time'
    
    # Create a new paginator
    paginator = Paginator(transactions.select_related('item', 'station', 'character', 'corp_wallet__corporation', 'other_char', 'other_corp'), 100)
    
    # Make sure page request is an int, default to 1st page
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    # If page request is out of range, deliver last page of results
    try:
        transactions = paginator.page(page)
    except (EmptyPage, InvalidPage):
        transactions = paginator.page(paginator.num_pages)
    
    data['transactions'] = transactions
    
    # Ready template things
    data['json_expected'] = json.dumps(FILTER_EXPECTED)
    data['values'] = {
        'chars': characters,
        'corps': corporations,
    }

    # Render template
    return render_to_response(
        'thing/transactions_item.html',
        data,
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
