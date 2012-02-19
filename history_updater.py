#!/usr/local/bin/python

import os
import psycopg2
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


HISTORY_URL = 'http://goonmetrics.com/api/price_history/?region_id=10000002&type_id=%s'

def main():
    cursor = connection.cursor()
    
    # Get a list of all item_ids
    item_ids = []
    cursor.execute("""
    SELECT  item_id
FROM    thing_marketorder
UNION
SELECT  bp.item_id
FROM    thing_blueprint bp, thing_blueprintinstance bpi
WHERE   bp.id = bpi.blueprint_id
UNION
SELECT  item_id
FROM    thing_blueprintcomponent
WHERE   blueprint_id IN (
            SELECT  blueprint_id
            FROM    thing_blueprintinstance
)
    """)
    for row in cursor:
        item_ids.append(row[0])
    
    item_ids = list(item_ids)
    item_ids.sort()
    
    # Collect data
    for i in range(0, len(item_ids), 50):
        # Fetch the XML
        url = HISTORY_URL % (','.join(str(z) for z in item_ids[i:i+50]))
        f = urllib2.urlopen(url)
        data = f.read()
        f.close()
        root = ET.fromstring(data)
        
        # Do stuff
        for t in root.findall('price_history/type'):
            type_id = t.attrib['id']
            
            data = {}
            for h in t.findall('history'):
                date = h.attrib['date']
                minPrice = h.attrib['minPrice']
                maxPrice = h.attrib['maxPrice']
                avgPrice = h.attrib['avgPrice']
                movement = h.attrib['movement']
                numOrders = h.attrib['numOrders']
                
                data[date] = (minPrice, maxPrice, avgPrice, movement, numOrders)
            
            # Query that shit
            for ph in PriceHistory.objects.filter(region=10000002, item=type_id, date__in=data.keys()):
                del data[str(ph.date)]
            
            # Add new ones
            for date, row in data.items():
                ph = PriceHistory(
                    region_id=10000002,
                    item_id=type_id,
                    date=date,
                    minimum=row[0],
                    maximum=row[1],
                    average=row[2],
                    movement=row[3],
                    orders=row[4],
                )
                ph.save()


if __name__ == '__main__':
    main()
