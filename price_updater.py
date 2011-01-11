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


QUICKLOOK_URL = 'http://api.goonfleet.com:8080/api/quicklook?typeid=%s&usesystem=30000142'


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
	for item_id in item_ids:
		item = Item.objects.filter(pk=item_id)[0]
		
		# Retrieve quicklook data and parse the XML
		url = QUICKLOOK_URL % (item_id)
		f = urllib2.urlopen(url)
		data = f.read()
		f.close()
		root = ET.fromstring(data)
		
		# Find a not quite bottom sell order
		sell_orders = root.findall('quicklook/sell_orders/order')
		if not sell_orders:
			continue
		n = min(2, len(sell_orders) - 1)
		item.sell_price = Decimal(sell_orders[n].find('price').text)
		
		# Find a not quite bottom buy order
		buy_orders = root.findall('quicklook/buy_orders/order')
		if not buy_orders:
			continue
		n = min(2, len(buy_orders) - 1)
		item.buy_price = Decimal(buy_orders[n].find('price').text)
		
		item.save()
		
		time.sleep(1)

if __name__ == '__main__':
	main()
