import requests

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from django.db import connection

from thing import queries
from thing.models import *

from celery import task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

# ---------------------------------------------------------------------------

HEADERS = {
    'User-Agent': 'EVEthing-tasks',
}

# ---------------------------------------------------------------------------
# Periodic task to retrieve current Jita price data from Goonmetrics
PRICE_PER_REQUEST = 100
PRICE_URL = 'http://goonmetrics.com/api/price_data/?station_id=60003760&type_id=%s'

@task
def price_updater():
    # Get a list of all item_ids
    cursor = connection.cursor()
    cursor.execute(queries.all_item_ids)

    item_ids = []
    for row in cursor:
        item_ids.append(row[0])

    cursor.close()

    # Bulk retrieve items
    item_map = Item.objects.in_bulk(item_ids)

    for i in range(0, len(item_ids), PRICE_PER_REQUEST):
        # Retrieve market data and parse the XML
        url = PRICE_URL % (','.join(str(item_id) for item_id in item_ids[i:i+PRICE_PER_REQUEST]))
        r = requests.get(url, headers=HEADERS)
        root = ET.fromstring(r.text)
        
        # Update item prices
        for t in root.findall('price_data/type'):
            item = item_map[int(t.attrib['id'])]
            item.buy_price = t.find('buy/max').text
            item.sell_price = t.find('sell/min').text
            item.save()

# ---------------------------------------------------------------------------
# Periodic task to retrieve Jita history data from Goonmetrics
HISTORY_PER_REQUEST = 50
HISTORY_URL = 'http://goonmetrics.com/api/price_history/?region_id=10000002&type_id=%s'

@task
def history_updater():
    # Get a list of all item_ids
    cursor = connection.cursor()
    cursor.execute(queries.all_item_ids)
    
    item_ids = []
    for row in cursor:
        item_ids.append(row[0])

    cursor.close()

    # Collect data
    new = []
    for i in range(0, len(item_ids), 50):
        # Fetch the XML
        url = HISTORY_URL % (','.join(str(z) for z in item_ids[i:i+50]))
        r = requests.get(url, headers=HEADERS)
        root = ET.fromstring(r.text)
        
        # Do stuff
        for t in root.findall('price_history/type'):
            type_id = int(t.attrib['id'])
            
            data = {}
            for hist in t.findall('history'):
                data[hist.attrib['date']] = hist
            
            # Query that shit
            for ph in PriceHistory.objects.filter(region=10000002, item=type_id, date__in=data.keys()):
                del data[str(ph.date)]
            
            # Add new ones
            for date, hist in data.items():
                new.append(PriceHistory(
                    region_id=10000002,
                    item_id=type_id,
                    date=hist.attrib['date'],
                    minimum=hist.attrib['minPrice'],
                    maximum=hist.attrib['maxPrice'],
                    average=hist.attrib['avgPrice'],
                    movement=hist.attrib['movement'],
                    orders=hist.attrib['numOrders'],
                ))

    if new:
        PriceHistory.objects.bulk_create(new)

# ---------------------------------------------------------------------------
