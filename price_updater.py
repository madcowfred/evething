#!/usr/local/bin/python

import os
import time
import urllib2
import xml.etree.ElementTree as ET

# Aurgh
from django.core.management import setup_environ
import settings
setup_environ(settings)

from rdi.models import *


PRICE_URL = 'http://www.eve-metrics.com/api/item.xml?type_ids=%s&region_ids=10000002'


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
	item_ids = [str(item_id) for item_id in item_ids]
	
	# Fetch market data and write to the database
	for i in range(0, len(item_ids), 25):
		url = PRICE_URL % (','.join(item_ids[i:i+25]))
		f = urllib2.urlopen(url)
		data = f.read()
		f.close()
		root = ET.fromstring(data)
		
		# Items ho
		for t in root.findall('type'):
			item = Item.objects.get(pk=t.attrib['id'])
			item.buy_price = t.find('region/buy/simulated').text
			item.sell_price = t.find('region/sell/simulated').text
			item.save()


if __name__ == '__main__':
	main()
