import sqlite3
import urllib2
import xml.etree.ElementTree as ET


MARKET_URL = 'http://api.eve-central.com/api/marketstat?hours=72&%s'


def main():
	conn = sqlite3.connect('everdi.db')
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
	
	rows = list(rows)
	
	# Fetch market data and write to the database
	for i in range(0, len(rows), 20):
		url = MARKET_URL % ('&'.join('typeid=%s' % item for item in rows[i:i+20]))
		f = urllib2.urlopen(url)
		data = f.read()
		f.close()
		
		root = ET.fromstring(data)
		for t in root.findall('marketstat/type'):
			typeid = t.get('id')
			sell_median = t.find('sell/median').text
			buy_median = t.find('buy/median').text
			
			cur.execute('UPDATE rdi_item SET sell_median=?, buy_median=? WHERE id=?', (sell_median, buy_median, typeid))
		
		conn.commit()

if __name__ == '__main__':
	main()
