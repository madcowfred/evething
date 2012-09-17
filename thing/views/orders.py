try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

#from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
#from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.template import RequestContext

from coffin.shortcuts import *

from thing.models import *
from thing.stuff import dictfetchall, total_seconds
from thing import queries

# ---------------------------------------------------------------------------

ORDER_SLOT_SKILLS = {
    'Trade': 4,
    'Retail': 8,
    'Wholesale': 16,
    'Tycoon': 32,
}

# ---------------------------------------------------------------------------
# Market orders
@login_required
def orders(request):
    # Retrieve order aggregate data
    cursor = connection.cursor()
    cursor.execute(queries.order_aggregation, (request.user.id,))
    char_orders = OrderedDict()
    for row in dictfetchall(cursor):
        row['slots'] = 5
        char_orders[row['character_id']] = row

    # Retrieve trade skills that we're interested in
    order_cs = CharacterSkill.objects.filter(character__apikeys__user=request.user, skill__item__name__in=ORDER_SLOT_SKILLS.keys())
    order_cs = order_cs.select_related('character__apikey', 'skill__item')

    #for cs in CharacterSkill.objects.select_related().filter(character__apikey__user=request.user, skill__item__name__in=ORDER_SLOT_SKILLS.keys()):
    for cs in order_cs:
        char_id = cs.character.id
        if char_id not in char_orders:
            continue

        char_orders[char_id]['slots'] += (cs.level * ORDER_SLOT_SKILLS.get(cs.skill.item.name, 0))

    # Calculate free slots
    for row in char_orders.values():
        row['free_slots'] = row['slots'] - row['corp_orders'] - row['personal_orders']

    total_row = {
        'free_slots': sum(row['free_slots'] for row in char_orders.values()),
        'slots': sum(row['slots'] for row in char_orders.values()),
        'personal_orders': sum(row['personal_orders'] for row in char_orders.values()),
        'corp_orders': sum(row['corp_orders'] for row in char_orders.values()),
        'sell_orders': sum(row['sell_orders'] for row in char_orders.values()),
        'total_sells': sum(row['total_sells'] for row in char_orders.values()),
        'buy_orders': sum(row['buy_orders'] for row in char_orders.values()),
        'total_buys': sum(row['total_buys'] for row in char_orders.values()),
        'total_escrow': sum(row['total_escrow'] for row in char_orders.values()),
    }

    # Retrieve all orders
    orders = MarketOrder.objects.select_related('item', 'station', 'character', 'corp_wallet__corporation')
    orders = orders.filter(character__apikeys__user=request.user)
    orders = orders.order_by('station__name', '-buy_order', 'item__name')

    now = datetime.datetime.utcnow()
    for order in orders:
        order.z_remaining = total_seconds(order.expires - now)

    # Render template
    return render_to_response(
        'thing/orders.html',
        {
            'char_orders': char_orders,
            'orders': orders,
            'total_row': total_row,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
