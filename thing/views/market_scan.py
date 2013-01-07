from django.contrib.auth.decorators import login_required
from django.db import connection

from thing import queries
from thing.models import *
from thing.stuff import *

# ---------------------------------------------------------------------------
# Market scan
@login_required
def market_scan(request):
    cursor = connection.cursor()
    cursor.execute(queries.user_item_ids, (request.user.id, request.user.id, request.user.id))

    item_ids = []
    for row in cursor:
        item_ids.append(row[0])

    return render_page(
        'thing/market_scan.html',
        {
            'item_ids': item_ids,
        },
        request,
    )

# ---------------------------------------------------------------------------
