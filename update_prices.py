import os
import sqlite3
import time
import urllib2
import xml.etree.ElementTree as ET


QUICKLOOK_URL = 'http://api.eve-central.com/api/quicklook?typeid=%s&usesystem=30000142'


def main():
	db_filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'everdi.db')
	conn = sqlite3.connect(db_filepath)
	cur = conn.cursor()
	
	rows = set()
	
	# Get all items used in current BlueprintInstances as components
	cur.execute("""
SELECT DISTINCT c.item_id
FROM rdi_blueprintcomponent c
  INNER JOIN rdi_blueprintinstance AS bi
    ON c.blueprint_id = bi.blueprint_id
""")
	rows.update(cur.fetchall())
	
	# Get the final items made by all BlueprintInstances
	cur.execute("""
SELECT DISTINCT i.id
FROM rdi_item i
  INNER JOIN rdi_blueprint AS bp
    ON bp.item_id = i.id
  INNER JOIN rdi_blueprintinstance AS bi
    ON bi.blueprint_id = bp.id
""")
	rows.update(cur.fetchall())
	
	# Fetch market data and write to the database
	for row in rows:
		item_id = row[0]
		url = QUICKLOOK_URL % (item_id)
		f = urllib2.urlopen(url)
		data = f.read()
		f.close()
		
		root = ET.fromstring(data)
		
		sell_orders = root.findall('quicklook/sell_orders/order')
		if not sell_orders:
			continue
		n = min(2, len(sell_orders) - 1)
		sell_median = sell_orders[n].find('price').text
		
		buy_orders = root.findall('quicklook/buy_orders/order')
		if not buy_orders:
			continue
		n = min(2, len(buy_orders) - 1)
		buy_median = buy_orders[n].find('price').text
		
		cur.execute('UPDATE rdi_item SET sell_median=?, buy_median=? WHERE id=?', (sell_median, buy_median, item_id))
		conn.commit()
		
		time.sleep(1)

if __name__ == '__main__':
	main()
