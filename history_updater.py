#!/usr/local/bin/python

import os
import psycopg2
import time
import urllib2
import xml.etree.ElementTree as ET

# Aurgh
from django.core.management import setup_environ
import settings
setup_environ(settings)

from decimal import *

from thing.models import *


HISTORY_URL = 'http://eve-marketdata.com/api/item_history.xml?region_ids=10000002&type_ids=%s'


def main():
	conn = psycopg2.connect('dbname=%(NAME)s user=%(USER)s' % (settings.DATABASES['default'])) 
	cur = conn.cursor()
	
	# Get a list of items required to construct blueprint instances - I apologise, this is horrible
	item_ids = set()
	for bp_id in BlueprintInstance.objects.values_list('blueprint').distinct():
		for item_id in BlueprintComponent.objects.filter(blueprint=bp_id[0]).values_list('item'):
			item_ids.update((item_id[0],))
		
		item_ids.update((Blueprint.objects.filter(pk=bp_id[0])[0].item.id,))
	
	# Get a list of items we've traded in
	for item_id in Transaction.objects.values_list('item').distinct():
		item_ids.update(item_id)
	
	item_ids = list(item_ids)
	
	for i in range(0, len(item_ids), 25):
		# Work out the last date we have in the database for each item_id
		item_cache = {}
		last_date = {}
		for item_id in item_ids[i:i+25]:
			item_cache[item_id] = Item.objects.get(pk=item_id)
			
			histories = PriceHistory.objects.filter(item=item_id).order_by('-date')
			if histories.count() > 0:
				last_date[item_id] = '%s-%02d-%02d' % (histories[0].date.year, histories[0].date.month, histories[0].date.day)
		
		# Fetch the XML
		url = HISTORY_URL % (','.join('%s' % z for z in item_ids[i:i+25]))
		f = urllib2.urlopen(url)
		data = f.read()
		f.close()
		root = ET.fromstring(data)
		
		# Do stuff
		for t in root.iter('type'):
			#<type>
			#  <type_id>37</type_id>
			#  <region_id>10000002</region_id>
			#  <date>2011-04-17</date>
			#  <price_low>83.43</price_low>
			#  <price_high>88.61</price_high>
			#  <price_average>87.2</price_average>
			#  <quantity>492281316</quantity>
			#  <num_orders>1819</num_orders>
			#</type>
			date = t.find('date').text
			if date == '0000-00-00':
				continue
			item_id = int(t.find('type_id').text)
			price_low = t.find('price_low').text
			price_high = t.find('price_high').text
			price_average = t.find('price_average').text
			quantity = t.find('quantity').text
			num_orders = t.find('num_orders').text
			
			# If it's last_date, update
			#if last_date[item_id] and date == last_date[item_id]:
			#	histories[0].average = day.attrib['average']
			#	histories[0].maximum = day.attrib['maximum']
			#	histories[0].minimum = day.attrib['minimum']
			#	histories[0].movement = day.attrib['movement']
			#	histories[0].orders = day.attrib['orders']
			#	histories[0].save()
			
			# New one
			if (not item_id in last_date) or (item_id in last_date and date > last_date[item_id]):
				iph = PriceHistory(
                    region_id=10000002,
					item=item_cache[item_id],
					date=date,
					average=price_average,
					maximum=price_high,
					minimum=price_low,
					movement=quantity,
					orders=num_orders,
				)
				iph.save()


if __name__ == '__main__':
	main()
