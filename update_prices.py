import sqlite3
import urllib2
import xml.etree.ElementTree as ET


MARKET_URL = 'http://api.eve-central.com/api/marketstat?hours=24&%s'

ITEMS = [
	34, # Tritanium
	35, # Pyerite
	36, # Mexallon
	37, # Isogen
	38, # Nocxium
	39, # Zydrine
	40, # Megacyte
	11399, # Morphite
]


def main():
	conn = sqlite3.connect('everdi.db')
	cur = conn.cursor()
	
	url = MARKET_URL % ('&'.join('typeid=%s' % i for i in ITEMS))
	f = urllib2.urlopen(url)
	data = f.read()
	f.close()
	#open('data.txt', 'w').write(data)
	#data = open('data.txt').read()
	
	root = ET.fromstring(data)
	for t in root.findall('marketstat/type'):
		typeid = t.get('id')
		sell_median = t.find('sell/median').text
		buy_median = t.find('buy/median').text
		
		cur.execute('UPDATE blueprints_item SET sell_median=?, buy_median=? WHERE id=?', (sell_median, buy_median, typeid))
	
	conn.commit()

if __name__ == '__main__':
	main()
