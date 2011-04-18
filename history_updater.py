#!/usr/local/bin/python

import bz2
import csv
import datetime
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

#from local_settings import DATABASES
#from thing.models import *


#HISTORY_URL = 'http://eve-metrics.com/api/history.xml?type_ids=%s&days=90'
HISTORY_FILE = '10000002.csv.bz2'



def main():
	conn = psycopg2.connect('dbname=%(NAME)s user=%(USER)s' % (settings.DATABASES['default'])) 
	cur = conn.cursor()
	
	print time.time()
	
	histf = bz2.BZ2File(HISTORY_FILE)
	reader = csv.reader(histf)
	reader.next()
	
	current_id = None
	history = []
	for type_id, orders, movement, price_max, price_avg, price_min, date in csv.reader(histf):
		if current_id == type_id:
			history.append((int(type_id), date, int(orders), int(movement), Decimal(price_max), Decimal(price_avg), Decimal(price_min)))
		else:
			# Get the last history entry for this type_id
			cur.execute('SELECT date FROM thing_itempricehistory WHERE item_id = %s ORDER BY date DESC LIMIT 1', (current_id,))
			row = cur.fetchone()
			# If there is a latest database entry, filter anything older from history list
			if row is not None:
				last_date = '%s-%02d-%02d' % (row[0].year, row[0].month, row[0].day)
				history = [h for h in history if h[0] > last_date]
			
			print type_id, len(history)
			history.sort()
			cur.executemany('INSERT INTO thing_itempricehistory (item_id, date, orders, movement, maximum, average, minimum) VALUES (%s, %s, %s, %s, %s, %s, %s)',
				history)
			conn.commit()
			
			# Reset stuff
			current_id = type_id
			history = []
	
	print time.time()
	return
	
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
