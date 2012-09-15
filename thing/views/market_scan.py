#from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
#from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.template import RequestContext

from coffin.shortcuts import *

from thing.models import *
from thing import queries

# ---------------------------------------------------------------------------
# Market scan
@login_required
def market_scan(request):
    cursor = connection.cursor()
    cursor.execute(queries.user_item_ids, (request.user.id, request.user.id, request.user.id))

    item_ids = []
    for row in cursor:
        item_ids.append(row[0])

    return render_to_response(
        'thing/market_scan.html',
        {
            'item_ids': item_ids,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
