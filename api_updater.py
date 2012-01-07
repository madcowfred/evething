#!/usr/local/bin/python

import cPickle
import datetime
import os
import urllib2
import xml.etree.ElementTree as ET
from decimal import *
from urllib import urlencode

# Aurgh
from django.core.management import setup_environ
import settings
setup_environ(settings)

from thing.models import *


BASE_URL = 'http://eveapiproxy.wafflemonster.org'
CHARACTERS_URL = '%s/account/Characters.xml.aspx' % (BASE_URL)
ORDERS_CHAR_URL = '%s/char/MarketOrders.xml.aspx' % (BASE_URL)
ORDERS_CORP_URL = '%s/corp/MarketOrders.xml.aspx' % (BASE_URL)
TRANSACTIONS_CHAR_URL = '%s/char/WalletTransactions.xml.aspx' % (BASE_URL)
TRANSACTIONS_CORP_URL = '%s/corp/WalletTransactions.xml.aspx' % (BASE_URL)
WALLET_URL = '%s/corp/AccountBalance.xml.aspx' % (BASE_URL)

PADDING = datetime.timedelta(minutes=1)


class APIUpdater:
	def __init__(self):
		# Generate a character id map
		self.char_id_map = {}
		for character in Character.objects.all():
			self.char_id_map[character.eve_character_id] = character
	
	# Do the heavy lifting
	def go(self):
		for character in Character.objects.all():
			# Skip if they have no valid user_id/api_key
			if not character.eve_user_id or len(character.eve_api_key) != 64:
				continue
			
			# If their character id is not in the database, retrive and save it
			if not character.eve_character_id:
				root, times = fetch_api(CHARACTERS_URL, {}, character)
				err = root.find('error')
				if err is not None:
					show_error('character', err, times)
				else:
					for row in root.findall('result/rowset/row'):
						if row.attrib['name'].lower() == character.name.lower():
							character.name = row.attrib['name']
							character.eve_character_id = row.attrib['characterID']
							character.save()
			
			
			# Character things
			if not character.eve_api_corp:
				wallet = CorpWallet.objects.get(corporation=character.corporation, account_key=1000)
				self.fetch_transactions(character, wallet, for_corp=False)
				
				self.fetch_orders(character, is_corp=False)
			
			# Corporation things
			else:
				corporation = character.corporation
				
				# Update corporation wallet information/balances
				params = { 'characterID': character.eve_character_id }
				
				root, times = fetch_api(WALLET_URL, params, character)
				err = root.find('error')
				if err is not None:
					show_error('corpwallet', err, times)
					#print 'DEBUG: now: %s | bc: %s' % (datetime.datetime.now(), cache['corp'][corporation.name]['balances'])
				else:
					for row in root.findall('result/rowset/row'):
						accountID = int(row.attrib['accountID'])
						accountKey = int(row.attrib['accountKey'])
						balance = Decimal(row.attrib['balance'])
						
						wallets = CorpWallet.objects.filter(pk=accountID)
						# If the wallet exists, update the balance
						if wallets:
							wallets[0].balance = balance
							wallets[0].save()
						# Otherwise just make a new one
						else:
							wallet = CorpWallet(account_id=accountID, corporation=corporation, account_key=accountKey, balance=balance)
							wallet.save()
				
				# Update corporation transactions for each wallet
				for wallet in CorpWallet.objects.filter(corporation=corporation):
					self.fetch_transactions(character, wallet)
				
				# Update corporation orders
				self.fetch_orders(character)
	
	# Update corporation orders
	def fetch_orders(self, character, is_corp=True):
		params = { 'characterID': character.eve_character_id }
		
		if is_corp is True:
			url = ORDERS_CORP_URL
		else:
			url = ORDERS_CHAR_URL
		
		root, times = fetch_api(url, params, character)
		err = root.find('error')
		if err is not None:
			show_error('corporders', err, times)
		
		else:
			rows = root.findall('result/rowset/row')
			for row in rows:
				order_id = int(row.attrib['orderID'])
				orders = Order.objects.filter(pk=order_id)
				
				# Order exists
				if orders.count() > 0:
					order = orders[0]
					
					# Order is still active, update relevant details
					if row.attrib['orderState'] == '0':
						order.issued = parse_api_date(row.attrib['issued'])
						order.volume_remaining = int(row.attrib['volRemaining'])
						order.escrow = Decimal(row.attrib['escrow'])
						order.price = Decimal(row.attrib['price'])
						order.total_price = order.volume_remaining * order.price
						order.save()
					# Not active, nuke it from orbit
					else:
						order.delete()
				
				# Doesn't exist and is active, make a new order
				elif row.attrib['orderState'] == '0':
					if row.attrib['bid'] == '0':
						o_type = 'S'
					else:
						o_type = 'B'
					
					# Make sure the character charID is valid
					chars = Character.objects.filter(eve_character_id=row.attrib['charID'])
					if not chars:
						print 'ERROR: no matching Character object for charID=%s' % (row.attrib['charID'])
						continue
					
					# Make sure the item typeID is valid
					items = Item.objects.filter(pk=row.attrib['typeID'])
					if items.count() == 0:
						print "ERROR: item with typeID '%s' does not exist, what the fuck?" % (row.attrib['typeID'])
						print '>> attrib = %r' % (row.attrib)
						continue
					
					remaining = int(row.attrib['volRemaining'])
					price = Decimal(row.attrib['price'])
					order = Order(
						id=order_id,
						corporation=character.corporation,
						corp_wallet=CorpWallet.objects.filter(corporation=character.corporation, account_key=row.attrib['accountKey'])[0],
						character=chars[0],
						station=get_station(int(row.attrib['stationID']), 'UNKNOWN STATION'),
						item=items[0],
						issued=parse_api_date(row.attrib['issued']),
						o_type=o_type,
						volume_entered=int(row.attrib['volEntered']),
						volume_remaining=remaining,
						min_volume=int(row.attrib['minVolume']),
						duration=int(row.attrib['duration']),
						escrow=Decimal(row.attrib['escrow']),
						price=price,
						total_price=remaining*price,
					)
					order.save()
	
	# Fetch transactions and update the database
	def fetch_transactions(self, character, wallet, for_corp=True):
		# Initialise HTTP parameters
		params = {}
		params['characterID'] = character.eve_character_id
		if for_corp is True:
			params['accountKey'] = wallet.account_key
			url = TRANSACTIONS_CORP_URL
		else:
			url = TRANSACTIONS_CHAR_URL
		
		one_week_ago = None
		
		while True:
			root, times = fetch_api(url, params, character)
			err = root.find('error')
			if err is not None:
				# Fuck it, the API flat out lies about cache times
				if err.attrib['code'] not in ('101', '103'):
					show_error('fetch_transactions', err, times)
				break
			
			# We need to stop asking for data if the oldest transaction entry is older
			# than one week
			if one_week_ago is None:
				one_week_ago = times['current'] - datetime.timedelta(7)
			
			rows = root.findall('result/rowset/row')
			if not rows:
				break
			
			for row in rows:
				transaction_time = parse_api_date(row.attrib['transactionDateTime'])
				
				# Skip already seen transactions
				transaction_id = int(row.attrib['transactionID'])
				if Transaction.objects.filter(pk=transaction_id).count() > 0:
					continue
				
				# Make sure the item typeID is valid
				items = Item.objects.filter(pk=row.attrib['typeID'])
				if items.count() == 0:
					print "ERROR: item with typeID '%s' does not exist, what the fuck?" % (row.attrib['typeID'])
					print '>> attrib = %r' % (row.attrib)
					continue
				
				# Make the station object if it doesn't already exist
				station = get_station(int(row.attrib['stationID']), row.attrib['stationName'])
				
				# Make the transaction object
				if for_corp is True:
					try:
						char = self.char_id_map[int(row.attrib['characterID'])]
					except KeyError:
						print repr(row.attrib)
						raise
				else:
					char = character
				
				quantity = int(row.attrib['quantity'])
				price = Decimal(row.attrib['price'])
				
				t = Transaction(
					id=transaction_id,
					corporation=character.corporation,
					corp_wallet=wallet,
					character=char,
					date=transaction_time,
					t_type=row.attrib['transactionType'][0].upper(),
					station=station,
					item=items[0],
					quantity=quantity,
					price=price,
					total_price=quantity * price,
				)
				t.save()
				
				#print t.id, t.date, t.t_type, t.item, t.quantity, t.price
			
			# If we got 1000 rows we should retrieve some more
			#print 'DEBUG: rows: %d | cur: %s | owa: %s | tt: %s' % (len(rows), times['current'], one_week_ago, transaction_time)
			if len(rows) == 1000 and transaction_time > one_week_ago:
				params['beforeTransID'] = transaction_id
			else:
				break


def fetch_api(url, params, character):
	params['keyID'] = character.eve_user_id
	params['vCode'] = character.eve_api_key
	
	f = urllib2.urlopen(url, urlencode(params))
	data = f.read()
	f.close()
	
	root = ET.fromstring(data)
	times = {
		'current': parse_api_date(root.find('currentTime').text),
		'until': parse_api_date(root.find('cachedUntil').text),
	}
	times['delta'] = times['until'] - times['current']
	
	#print '%s | currentTime: %s | cachedUntil: %s | delta: %s' % (url, times['current'], times['until'], times['delta'])
	
	return (root, times)

def parse_api_date(s):
	return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')

def show_error(text, err, times):
	print '(%s) %s: %s | %s -> %s' % (text, err.attrib['code'], err.text, times['current'], times['until'])

# Caching station fetcher, adds unknown stations to the database
_station_cache = {}
def get_station(station_id, station_name):
	if station_id not in _station_cache:
		stations = Station.objects.filter(pk=station_id)
		if stations.count() > 0:
			station = stations[0]
			# Update the station name if it has changed recently
			if station.name != station_name:
				station.name = station_name
				station.save()
		else:
			station = Station(id=station_id, name=station_name)
			station.save()
		_station_cache[station_id] = station
	
	return _station_cache[station_id]

def main():
	updater = APIUpdater()
	updater.go()


if __name__ == '__main__':
	main()
