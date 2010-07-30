#!/usr/bin/env python

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


def main():
	_now = datetime.datetime.now
	
	# Load cache
	cache_filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache/cache.pickle')
	if os.path.exists(cache_filepath):
		cache = cPickle.load(open(cache_filepath, 'rb'))
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
				'transactions': datetime.datetime(1900, 1, 1),
			}
		
		# Update corporation wallet information/balances
		if _now() > cache['corp'][corporation.name]['balances']:
			root, delta = fetch_api(WALLET_URL, {'characterID': character.eve_character_id}, character)
			err = root.find('error')
			if err is not None:
				print "ERROR %s: %s" % (err.attrib['code'], err.text)
			else:
				cache['corp'][corporation.name]['balances'] = _now() + delta
				
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
		
		# Update corporation transactions
		if _now() > cache['corp'][corporation.name]['transactions']:
			for wallet in CorpWallet.objects.filter(corporation=corporation):
				# If this wallet already has some transactions, we can stop adding at the most recent one
				transactions = Transaction.objects.filter(corp_wallet=wallet).order_by('id')
				if transactions:
					stop_at = transactions[0].id
				else:
					stop_at = -1
				
				params = {
					'characterID': character.eve_character_id,
					'accountKey': wallet.account_key,
				}
				
				while 1:
					breakwhile = False
					
					cache_file = 'cache/%s_%s.xml' % (corporation.id, wallet.account_key)
					
					root, delta = fetch_api(TRANSACTIONS_URL, params, character)
					err = root.find('error')
					if err is not None:
						# Delay until later
						if err.attrib['code'] == '101':
							root = ET.fromstring(open(cache_file).read())
						else:
							print "ERROR %s: %s" % (err.attrib['code'], err.text)
							break
					else:
						open(cache_file, 'w').write(ET.tostring(root))
					
					#<row transactionDateTime="2008-08-04 22:01:00" transactionID="705664738" 
					#	quantity="50000" typeName="Oxygen Isotopes" typeID="17887" price="250.00" 
					#	clientID="174312871" clientName="ACHAR" characterID="000000000" 
					#	characterName="SELLER" stationID="60004375" 
					#	stationName="SYSTEM IV - Moon 10 - Corporate Police Force Testing Facilities" 
					#	transactionType="buy" transactionFor="corporation"/>
					rows = root.findall('result/rowset/row')
					if not rows:
						break
					
					for row in rows:
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
							id=int(row.attrib['transactionID']),
							corporation=corporation,
							corp_wallet=wallet,
							date=parse_api_date(row.attrib['transactionDateTime']),
							t_type=row.attrib['transactionType'][0].upper(),
							station=station,
							item=Item.objects.filter(pk=row.attrib['typeID'])[0],
							quantity=quantity,
							price=price,
							total_price=quantity * price,
						)
						t.save()
						
						print t.id, t.date, t.t_type, t.item, t.quantity, t.price
					
					# If we got 1000 rows we should retrieve some more
					if len(rows) == 1000:
						params['beforeTransID'] = t.id
					else:
						breakwhile = True
					
					if breakwhile:
						break
				
				cache['corp'][corporation.name]['transactions'] = _now() + delta
	
	# Save cache
	cPickle.dump(cache, open(cache_filepath, 'wb'))


def fetch_api(url, params, character):
	params['userID'] = character.eve_user_id
	params['apiKey'] = character.eve_api_key
	
	f = urllib2.urlopen(url, urlencode(params))
	data = f.read()
	f.close()
	
	root = ET.fromstring(data)
	current = parse_api_date(root.find('currentTime').text)
	until = parse_api_date(root.find('cachedUntil').text)
	
	return (root, until - current)

def parse_api_date(s):
	return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')


if __name__ == '__main__':
	main()
