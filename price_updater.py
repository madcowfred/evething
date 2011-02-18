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

from thing.models import *


MARKETSTAT_URL = 'http://api.goonfleet.com:8080/api/marketstat?regionlimit=10000002&usesystem=30000142&%s'


def main():
	# Get a list of items required to construct blueprint instances - I apologise, this is horrible
	item_ids = set()
	for bp_id in BlueprintInstance.objects.values_list('blueprint').distinct():
		for item_id in BlueprintComponent.objects.filter(blueprint=bp_id[0]).values_list('item'):
			item_ids.update((item_id[0],))
		
		item_ids.update((Blueprint.objects.filter(pk=bp_id[0])[0].item.id,))
	
	# Get a list of items in active orders
	for item_id in Order.objects.values_list('item').distinct():
		item_ids.update(item_id)
	
	# Fetch market data and write to the database
	item_ids = list(item_ids)
	item_ids.sort()
	
	for i in range(0, len(item_ids), 20):
		# Retrieve market data and parse the XML
		tstring = '&'.join('typeid=%s' % item_id for item_id in item_ids[i:i+20])
		url = MARKETSTAT_URL % (tstring)
		f = urllib2.urlopen(url)
		data = f.read()
		f.close()
		root = ET.fromstring(data)
		
		# Save market order shit
		for t in root.findall('marketstat/type'):
			item = Item.objects.get(pk=t.attrib['id'])
			item.buy_price = t.find('buy/max').text
			item.sell_price = t.find('sell/min').text
			item.save()
		
		time.sleep(1)


if __name__ == '__main__':
	main()
