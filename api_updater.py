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

from rdi.models import *


BASE_URL = 'http://api.eve-online.com'
CHARACTERS_URL = '%s/account/Characters.xml.aspx' % (BASE_URL)
ORDERS_URL = '%s/corp/MarketOrders.xml.aspx' % (BASE_URL)
TRANSACTIONS_URL = '%s/corp/WalletTransactions.xml.aspx' % (BASE_URL)
WALLET_URL = '%s/corp/AccountBalance.xml.aspx' % (BASE_URL)

PADDING = datetime.timedelta(minutes=1)


def main():
	_now = datetime.datetime.now
	
	# Load cache
	cache_path = os.path.dirname(os.path.abspath(__file__))
	pickle_filepath = os.path.join(cache_path, 'cache/cache.pickle')
	if os.path.exists(pickle_filepath):
		cache = cPickle.load(open(pickle_filepath, 'rb'))
	else:
		cache = {
			'char': {},
			'corp': {},
		}
	
	
	for character in Character.objects.all():
		# Skip if they have no valid user_id/api_key
		if not character.eve_user_id or len(character.eve_api_key) != 64:
			continue
		
		# Initialise cache
		if character.name not in cache['char']:
			cache['char'][character.name] = {}
		
		# Get their character ID if it has never been retrieved
		if not character.eve_character_id:
			root, times = fetch_api(CHARACTERS_URL, {}, character)
			err = root.find('error')
			if err is not None:
				show_error('character', err, times)
			else:
				for row in root.findall('result/rowset/row'):
					if row.attrib['name'].lower() == character.name.lower():
						character.eve_character_id = row.attrib['characterID']
						character.save()
		
		
		corporation = character.corporation
		
		# Initialise cache
		if corporation.name not in cache['corp']:
			cache['corp'][corporation.name] = {
				'balances': datetime.datetime(1900, 1, 1),
				'orders': datetime.datetime(1900, 1, 1),
				'transactions': {},
			}
		
		# Update corporation wallet information/balances
		if _now() > cache['corp'][corporation.name]['balances']:
			root, times = fetch_api(WALLET_URL, {'characterID': character.eve_character_id}, character)
			err = root.find('error')
			if err is not None:
				show_error('corpwallet', err, times)
				#print 'DEBUG: now: %s | bc: %s' % (_now(), cache['corp'][corporation.name]['balances'])
			else:
				for row in root.findall('result/rowset/row'):
					accountID = int(row.attrib['accountID'])
					accountKey = int(row.attrib['accountKey'])
					balance = Decimal(row.attrib['balance'])
					
					wallet = CorpWallet.objects.filter(pk=accountID)
					if wallet:
						wallet[0].balance = balance
						wallet[0].save()
					else:
						wallet = CorpWallet(account_id=accountID, corporation=corporation, account_key=accountKey, balance=balance)
						wallet.save()
			
			cache['corp'][corporation.name]['balances'] = _now() + times['delta'] + PADDING
		
		
		# Update corporation transactions
		tcache = cache['corp'][corporation.name]['transactions']
		for wallet in CorpWallet.objects.filter(corporation=corporation):
			wak = wallet.account_key
			if wak in tcache and _now() < tcache[wak]:
				continue
			
			params = {
				'characterID': character.eve_character_id,
				'accountKey': wak,
			}
			
			one_week_ago = None
			
			while 1:
				root, times = fetch_api(TRANSACTIONS_URL, params, character)
				err = root.find('error')
				if err is not None:
					# Fuck it, the API flat out lies about cache times
					if err.attrib['code'] not in ('101', '103'):
						show_error('corptrans', err, times)
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
					if Transaction.objects.filter(pk=transaction_id):
						continue
					
					# Make the station object if it doesn't already exist
					station = rdi_station(int(row.attrib['stationID']), row.attrib['stationName'])
					
					# Make the transaction object
					quantity = int(row.attrib['quantity'])
					price = Decimal(row.attrib['price'])
					t = Transaction(
						id=transaction_id,
						corporation=corporation,
						corp_wallet=wallet,
						date=transaction_time,
						t_type=row.attrib['transactionType'][0].upper(),
						station=station,
						item=Item.objects.filter(pk=row.attrib['typeID'])[0],
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
			
			#print 'DEBUG: tcw: %s' % (tcache.get(wak, 0))
			tcache[wak] = _now() + times['delta'] + PADDING
			#print 'DEBUG: wak: %s | now: %s | tcw: %s' % (wak, _now(), tcache[wak])
		
		
		# Update corporation orders
		if _now() > cache['corp'][corporation.name]['orders']:
			params = {
				'characterID': character.eve_character_id,
			}
			
			root, times = fetch_api(ORDERS_URL, params, character)
			err = root.find('error')
			if err is not None:
				# Fuck it, the API flat out lies about cache times
				#if err.attrib['code'] not in ('101', '103'):
				show_error('corporders', err, times)
				break
			
			rows = root.findall('result/rowset/row')
			if not rows:
				break
			
			for row in rows:
				order_id = int(row.attrib['orderID'])
				orders = Order.objects.filter(pk=order_id)
				
				# Hey, this transaction already exists
				if orders:
					order = orders[0]
					
					# Order is active, update stuff I guess
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
					
					chars = Character.objects.filter(eve_character_id=row.attrib['charID'])
					if not chars:
						print 'ERROR: no matching Character object for charID=%s' % (row.attrib['charID'])
						continue
					
					remaining = int(row.attrib['volRemaining'])
					price = Decimal(row.attrib['price'])
					order = Order(
						id=order_id,
						corporation=corporation,
						corp_wallet=CorpWallet.objects.filter(corporation=corporation, account_key=row.attrib['accountKey'])[0],
						character=chars[0],
						station=rdi_station(int(row.attrib['stationID']), 'UNKNOWN STATION'),
						item=Item.objects.filter(pk=int(row.attrib['typeID']))[0],
						issued=parse_api_date(row.attrib['issued']),
						o_type=o_type,
						volume_entered=int(row.attrib['volEntered']),
						volume_remaining=remaining,
						min_volume=int(row.attrib['minVolume']),
						duration=int(row.attrib['duration']),
						escrow=Decimal(row.attrib['escrow']),
						price=price,
						total_price=volume_remaining*price,
					)
					order.save()
					
					#print t.id, t.date, t.t_type, t.item, t.quantity, t.price
			
			cache['corp'][corporation.name]['orders'] = _now() + times['delta'] + PADDING
	
	
	# Save cache
	cPickle.dump(cache, open(pickle_filepath, 'wb'))


def fetch_api(url, params, character):
	#print 'params: %s' % (params)
	params['userID'] = character.eve_user_id
	params['apiKey'] = character.eve_api_key
	
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

def rdi_station(station_id, station_name):
	station = Station.objects.filter(pk=station_id)
	if station:
		station = station[0]
	else:
		station = Station(id=station_id, name=station_name)
		station.save()
	return station


if __name__ == '__main__':
	main()
