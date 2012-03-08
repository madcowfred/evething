#!/usr/local/bin/python

import os
import time
import urllib2
import xml.etree.ElementTree as ET
from decimal import *

# Aurgh
from django.core.management import setup_environ
import settings
setup_environ(settings)

from django.db import connection
from thing.models import *
from thing import queries


PER_REQUEST = 100
PRICE_URL = 'http://goonmetrics.com/api/price_data/?station_id=60003760&type_id=%s'


def main():
    cursor = connection.cursor()
    
    # Get a list of all item_ids
    item_ids = []
    cursor.execute(queries.all_item_ids)
    for row in cursor:
        item_ids.append(row[0])

    # Fetch market data and write to the database
    for i in range(0, len(item_ids), PER_REQUEST):
        # Retrieve market data and parse the XML
        tstring = ','.join(str(item_id) for item_id in item_ids[i:i+PER_REQUEST])
        url = PRICE_URL % (tstring)
        f = urllib2.urlopen(url)
        data = f.read()
        f.close()
        root = ET.fromstring(data)
        
        # Save market order shit
        for t in root.findall('price_data/type'):
            item = Item.objects.get(pk=t.attrib['id'])
            item.buy_price = t.find('buy/max').text
            item.sell_price = t.find('sell/min').text
            item.save()


if __name__ == '__main__':
    main()
