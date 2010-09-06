#!/usr/local/bin/python

import os
import time
import urllib2
import xml.etree.ElementTree as ET

# Aurgh
from django.core.management import setup_environ
import settings
setup_environ(settings)

from thing.models import *


HISTORY_URL = 'http://eve-metrics.com/api/history.xml?type_ids=%s&days=90'


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
	
	# Fetch gigantic history data and write to the database
	for i in range(0, len(item_ids), 25):
		url = HISTORY_URL % (','.join(item_ids[i:i+25]))
		f = urllib2.urlopen(url)
		data = f.read()
		f.close()
		root = ET.fromstring(data)
		
		# Tally ho
		for t in root.findall('type'):
			item_id = t.attrib['id']
			
			# If there is previous history we need to stop after we do the last one
			histories = ItemPriceHistory.objects.filter(item=item_id)
			if histories.count() != 0:
				hdate = histories[0].date
				last_date = '%s-%02d-%02d' % (hdate.year, hdate.month, hdate.day)
			else:
				last_date = None
			
			# Blah blah blah
			# <day average="2.46" maximum="2.49" minimum="2.43" movement="50169516131" orders="2818">2010-08-02</day>
			for day in t.findall('global/history/day'):
				date = day.text
				
				# If it's last_date, update and bail
				if last_date and date == last_date:
					histories[0].average = day.attrib['average']
					histories[0].maximum = day.attrib['maximum']
					histories[0].minimum = day.attrib['minimum']
					histories[0].movement = day.attrib['movement']
					histories[0].orders = day.attrib['orders']
					histories[0].save()
					break
				
				# New one
				else:
					iph = ItemPriceHistory(
						item=Item.objects.get(pk=item_id),
						date=date,
						average=day.attrib['average'],
						maximum=day.attrib['maximum'],
						minimum=day.attrib['minimum'],
						movement=day.attrib['movement'],
						orders=day.attrib['orders'],
					)
					iph.save()

if __name__ == '__main__':
	main()
