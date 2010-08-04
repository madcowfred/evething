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
			root, delta = fetch_api(CHARACTERS_URL, {}, character)
			err = root.find('error')
			if err is not None:
				print "ERROR %s: %s" % (err.attrib['code'], err.text)
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
				'transactions': {},
			}
		
		# Update corporation wallet information/balances
		if _now() > cache['corp'][corporation.name]['balances']:
			root, times = fetch_api(WALLET_URL, {'characterID': character.eve_character_id}, character)
			err = root.find('error')
			if err is not None:
				show_error('corpwallet', err, times)
				print _now(), tcache.get(wak, None)
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
				root, delta = fetch_api(TRANSACTIONS_URL, params, character)
				err = root.find('error')
				if err is not None:
					show_error('corptrans', err, times)
					print _now(), tcache.get(wak, None)
					break
				
				# We need to stop asking for data if the oldest transaction entry is older
				# than one week
				if one_week_ago is None:
					one_week_ago = parse_api_date(root.find('currentTime').text) - datetime.timedelta(7)
				
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
					station_id = int(row.attrib['stationID'])
					station = Station.objects.filter(pk=station_id)
					if station:
						station = station[0]
					else:
						station = Station(id=station_id, name=row.attrib['stationName'])
						station.save()
					
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
				if len(rows) == 1000 and transaction_time > one_week_ago:
					params['beforeTransID'] = t.id
				else:
					break
			
			tcache[wak] = _now() + times['delta'] + PADDING
			print 'DEBUG: %s | %s | %s || %s | %s | %s' % (wak, _now(), tcache[wak], times['current'], times['until'], times['delta'])
	
	# Save cache
	cPickle.dump(cache, open(pickle_filepath, 'wb'))


def fetch_api(url, params, character):
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
	
	print 'DEBUG: %s | currentTime: %s | cachedUntil: %s | delta: %s' % (url, times['current'], times['until'], times['delta'])
	
	return (root, times)

def parse_api_date(s):
	return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')

def show_error(text, err, times):
	print '(%s) %s: %s | %s -> %s' % (text, err.attrib['code'], err.text, times['current'], times['until'])


if __name__ == '__main__':
	main()
