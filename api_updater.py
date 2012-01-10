#!/usr/local/bin/python

import datetime
import os
import sys
import urllib2
import xml.etree.ElementTree as ET
from decimal import *
from urllib import urlencode

# Aurgh
from django.core.management import setup_environ
import settings
setup_environ(settings)

from django.db.models import Q

from thing.models import *

# my API proxy, you should probably either run your own or uncomment the second line
BASE_URL = 'http://eveapiproxy.wafflemonster.org'
#BASE_URL = 'http://api.eveonline.com'

API_INFO_URL = '%s/account/APIKeyInfo.xml.aspx' % (BASE_URL)
BALANCE_URL = '%s/corp/AccountBalance.xml.aspx' % (BASE_URL)
CHARACTERS_URL = '%s/account/Characters.xml.aspx' % (BASE_URL)
CORP_SHEET_URL = '%s/corp/CorporationSheet.xml.aspx' % (BASE_URL)
ORDERS_CHAR_URL = '%s/char/MarketOrders.xml.aspx' % (BASE_URL)
ORDERS_CORP_URL = '%s/corp/MarketOrders.xml.aspx' % (BASE_URL)
TRANSACTIONS_CHAR_URL = '%s/char/WalletTransactions.xml.aspx' % (BASE_URL)
TRANSACTIONS_CORP_URL = '%s/corp/WalletTransactions.xml.aspx' % (BASE_URL)


class APIUpdater:
    def __init__(self, debug=False):
        self.debug = debug
    
    # -----------------------------------------------------------------------
    # Do the heavy lifting
    def go(self):
        # Make sure API keys are valid and various character things are up to date
        for apikey in APIKey.objects.filter(valid=True):
            self.api_check(apikey)

        # Generate a character id map
        self.char_id_map = {}
        for character in Character.objects.all():
            self.char_id_map[character.eve_character_id] = character
        
        # Now we can get down to business
        for apikey in APIKey.objects.filter(valid=True):
            # Account/Character key are basically the same thing
            if apikey.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
                for character in apikey.character_set.all():
                    # Fetch wallet transactions
                    self.fetch_transactions(apikey, character)
                    
                    # Fetch market orders
                    self.fetch_orders(apikey, character)
            
            # Corporation key
            elif apikey.key_type == APIKey.CORPORATION_TYPE:
                character = apikey.corp_character
                corporation = character.corporation
                
                # Update wallet information first
                self.fetch_corp_wallets(apikey)
                
                # Update corporate sheet information (wallet division names)
                self.fetch_corp_sheet(apikey)
                
                # Update things for each corp wallet
                for corpwallet in CorpWallet.objects.filter(corporation=corporation):
                    # Fetch wallet transactions
                    self.fetch_transactions(apikey, character, corp_wallet=corpwallet)
                
                # Fetch market orders
                self.fetch_orders(apikey, character)
        
        # All done, clean up any out-of-date cached API requests
        now = datetime.datetime.utcnow()
        APICache.objects.filter(cached_until__lt=now).delete()
    
    # -----------------------------------------------------------------------
    # Do various API key things
    def api_check(self, apikey):
        root, times = self.fetch_api(API_INFO_URL, {}, apikey)
        
        # Check for errors
        err = root.find('error')
        if err is not None:
            # 202/203/204/205/210/212 Authentication failure
            # 207 Not available for NPC corporations
            # 220 Invalid corporate key
            # 222 Key has expired
            # 223 Legacy API key
            if err.attrib['code'] in ('202', '203', '204', '205', '210', '212', '207', '220', '222', '223'):
                apikey.valid = False
                apikey.save()
            show_error('apicheck', err, times)
            return
        
        # Find the key node
        key_node = root.find('result/key')
        # Update access mask
        apikey.access_mask = int(key_node.attrib['accessMask'])
        # Update expiry date
        expires = key_node.attrib['expires']
        if expires:
            apikey.expires = parse_api_date(expires)
        # Update key type
        apikey.key_type = key_node.attrib['type']
        # Save
        apikey.save()
        
        # Handle character key type keys
        if key_node.attrib['type'] in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
            seen_chars = []
            
            for row in key_node.findall('rowset/row'):
                characterID = row.attrib['characterID']
                seen_chars.append(characterID)
                
                # Get a corporation object
                corp = get_corporation(row.attrib['corporationID'], row.attrib['corporationName'])
                
                characters = Character.objects.filter(eve_character_id=characterID)
                # Character doesn't exist, make a new one and save it
                if characters.count() == 0:
                    character = Character(
                        apikey=apikey,
                        eve_character_id=characterID,
                        name=row.attrib['characterName'],
                        corporation=corp,
                    )
                # Character exists, update API key and corporation information
                else:
                    character = characters[0]
                    character.apikey = apikey
                    character.corporation = corp
                
                # Save the character
                character.save()
            
            # Unlink any characters that are no longer valid for this API key
            for character in Character.objects.filter(apikey=apikey).exclude(pk__in=seen_chars):
                character.apikey = None
                character.save()
        
        # Handle corporate key
        elif key_node.attrib['type'] == APIKey.CORPORATION_TYPE:
            row = key_node.find('rowset/row')
            characterID = row.attrib['characterID']
            
            # Get a corporation object
            corp = get_corporation(row.attrib['corporationID'], row.attrib['corporationName'])
            
            characters = Character.objects.filter(eve_character_id=characterID)
            # Character doesn't exist, make a new one and save it
            if characters.count() == 0:
                character = Character(
                    eve_character_id=characterID,
                    name=row.attrib['characterName'],
                    corporation=corp,
                )
            else:
                character = characters[0]
            
            apikey.corp_character = character
            apikey.save()
    
    # -----------------------------------------------------------------------
    # Fetch and add/update corporation wallets
    def fetch_corp_wallets(self, apikey):
        # Make sure the access mask matches
        if (apikey.access_mask & 1) == 0:
            return
        
        params = { 'characterID': apikey.corp_character_id }
        
        root, times = self.fetch_api(BALANCE_URL, params, apikey)
        err = root.find('error')
        if err is not None:
            show_error('corpwallets', err, times)
            return
        
        corporation = apikey.corp_character.corporation

        for row in root.findall('result/rowset/row'):
            accountID = int(row.attrib['accountID'])
            accountKey = int(row.attrib['accountKey'])
            balance = Decimal(row.attrib['balance'])
            
            wallets = CorpWallet.objects.filter(pk=accountID)
            # If the wallet exists, update the balance
            if wallets:
                wallet = wallets[0]
                wallet.balance = balance
                wallet.save()
            # Otherwise just make a new one
            else:
                wallet = CorpWallet(
                    account_id=accountID,
                    corporation=corporation,
                    account_key=accountKey,
                    description='',
                    balance=balance
                )
                wallet.save()
    
    # -----------------------------------------------------------------------
    # Fetch the corporation sheet
    def fetch_corp_sheet(self, apikey):
        # Make sure the access mask matches
        if (apikey.access_mask & 8) == 0:
            return
        
        params = { 'characterID': apikey.corp_character_id }
        
        root, times = self.fetch_api(CORP_SHEET_URL, params, apikey)
        err = root.find('error')
        if err is not None:
            show_error('corpsheet', err, times)
            return
        
        corporation = apikey.corp_character.corporation
        
        for rowset in root.findall('result/rowset'):
            if rowset.attrib['name'] == 'walletDivisions':
                for row in rowset.findall('row'):
                    wallets = CorpWallet.objects.filter(corporation=corporation, account_key=row.attrib['accountKey'])
                    # Wallet division doesn't exist, this is bad
                    if wallets.count() == 0:
                        print 'ERROR: no matching CorpWallet object for corpID=%s accountKey=%s' % (corporation.id, row.attrib['accountKey'])
                    # Wallet division exists, update description
                    else:
                        wallet = wallets[0]
                        wallet.description = row.attrib['description']
                        wallet.save()
    
    # -----------------------------------------------------------------------
    # Fetch and add/update orders
    def fetch_orders(self, apikey, character):
        # Initalise stuff
        if apikey.corp_character:
            mask = 4096
            url = ORDERS_CORP_URL
        else:
            mask = 4096
            url = ORDERS_CHAR_URL
        
        # Make sure the access mask matches
        if (apikey.access_mask & mask) == 0:
            return
        
        # Fetch the API data
        params = { 'characterID': character.eve_character_id }
        root, times = self.fetch_api(url, params, apikey)
        err = root.find('error')
        if err is not None:
            show_error('corporders', err, times)
            return
        
        # Iterate over the returned result set
        for row in root.findall('result/rowset/row'):
            order_id = int(row.attrib['orderID'])
            orders = Order.objects.filter(order_id=order_id, character=character)
            
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
                if chars.count() == 0:
                    print 'ERROR: no matching Character object for charID=%s' % (row.attrib['charID'])
                    continue
                
                # Make sure the item typeID is valid
                #items = Item.objects.filter(pk=row.attrib['typeID'])
                #if items.count() == 0:
                #    print "ERROR: item with typeID '%s' does not exist, what the fuck?" % (row.attrib['typeID'])
                #    print '>> attrib = %r' % (row.attrib)
                #    continue
                
                # Create a new order and save it
                remaining = int(row.attrib['volRemaining'])
                price = Decimal(row.attrib['price'])
                order = Order(
                    order_id=order_id,
                    character=chars[0],
                    station=get_station(int(row.attrib['stationID']), 'UNKNOWN STATION'),
                    item=get_item(row.attrib['typeID']),
                    issued=parse_api_date(row.attrib['issued']),
                    o_type=o_type,
                    volume_entered=int(row.attrib['volEntered']),
                    volume_remaining=remaining,
                    min_volume=int(row.attrib['minVolume']),
                    duration=int(row.attrib['duration']),
                    escrow=Decimal(row.attrib['escrow']),
                    price=price,
                    total_price=remaining * price,
                )
                # Set the corp_wallet for corporation API requests
                if apikey.corp_character:
                    order.corp_wallet = CorpWallet.objects.get(corporation=character.corporation, account_key=row.attrib['accountKey'])
                order.save()
    
    # -----------------------------------------------------------------------
    # Fetch transactions and update the database
    def fetch_transactions(self, apikey, character, corp_wallet=None):
        # Initialise stuff
        params = { 'characterID': character.eve_character_id }
        if apikey.corp_character:
            params['accountKey'] = corp_wallet.account_key
            mask = 2097152
            url = TRANSACTIONS_CORP_URL
        else:
            mask = 4194304
            url = TRANSACTIONS_CHAR_URL
        
        # Make sure the access mask matches
        if (apikey.access_mask & mask) == 0:
            return
        
        # Aaaaa
        if self.debug:
            start = time.time()
            
        # Set up the transactions filter
        if apikey.corp_character:
            transactions = Transaction.objects.filter(corp_wallet=corp_wallet)
        else:
            transactions = Transaction.objects.filter(character=character)
        
        # Loop until we run out of transactions
        one_week_ago = None
        while True:
            root, times = self.fetch_api(url, params, apikey)
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
                # Initalise some variables
                transaction_id = int(row.attrib['transactionID'])
                transaction_time = parse_api_date(row.attrib['transactionDateTime'])
                
                # Skip corporate transactions if this is a personal call, we have no idea
                # what wallet this transaction is related to otherwise :ccp:
                if not apikey.corp_character and row.attrib['transactionFor'] == 'corporation':
                    continue
                
                # Check to see if this transaction already exists
                if transactions.filter(transaction_id=transaction_id, date=transaction_time).count():
                    continue
                
                # Make sure the item typeID is valid
                #items = Item.objects.filter(pk=row.attrib['typeID'])
                #if items.count() == 0:
                #    print "ERROR: item with typeID '%s' does not exist, what the fuck?" % (row.attrib['typeID'])
                #    print '>> attrib = %r' % (row.attrib)
                #    continue
                
                # Make the station object if it doesn't already exist
                station = get_station(int(row.attrib['stationID']), row.attrib['stationName'])
                
                # Work out what the character should be
                if apikey.corp_character:
                    try:
                        char = self.char_id_map[int(row.attrib['characterID'])]
                    except KeyError:
                        print repr(row.attrib)
                        raise
                else:
                    char = character
                
                # Create a new transaction object and save it
                quantity = int(row.attrib['quantity'])
                price = Decimal(row.attrib['price'])
                
                t = Transaction(
                    transaction_id=transaction_id,
                    character=char,
                    date=transaction_time,
                    t_type=row.attrib['transactionType'][0].upper(),
                    station=station,
                    item=get_item(row.attrib['typeID']),
                    quantity=quantity,
                    price=price,
                    total_price=quantity * price,
                )
                # Set the corp_character for corporation API requests
                if apikey.corp_character:
                    t.corp_wallet = corp_wallet
                t.save()
            
            # If we got 1000 rows we should retrieve some more
            #print 'DEBUG: rows: %d | cur: %s | owa: %s | tt: %s' % (len(rows), times['current'], one_week_ago, transaction_time)
            if len(rows) == 1000 and transaction_time > one_week_ago:
                params['beforeTransID'] = transaction_id
            else:
                break
        
        if self.debug:
            print 'transactions took %.2fs' % (time.time() - start)

    # ---------------------------------------------------------------------------
    # Perform an API request and parse the returned XML via ElementTree
    def fetch_api(self, url, params, apikey):
        # Add the API key information
        params['keyID'] = apikey.id
        params['vCode'] = apikey.vcode
        
        # Check the API cache for this URL/params combo
        now = datetime.datetime.utcnow()
        params_repr = repr(sorted(params.items()))
        apicaches = APICache.objects.filter(url=url, parameters=params_repr, cached_until__gt=now)
        # Data is cached, use that
        if apicaches.count() > 0:
            if self.debug:
                print 'API: %s CACHED' % (url)
            data = apicaches[0].text
        # Data is not cached, fetch new data
        else:
            if self.debug:
                print 'API: %s...' % (url),
                sys.stdout.flush()
            
            # Fetch the URL
            f = urllib2.urlopen(url, urlencode(params))
            data = f.read()
            f.close()
            
            if self.debug:
                print '%s' % (datetime.datetime.utcnow() - now)
        
        # Parse the XML
        root = ET.fromstring(data)
        times = {
            'current': parse_api_date(root.find('currentTime').text),
            'until': parse_api_date(root.find('cachedUntil').text),
        }
        
        # If the data wasn't cached, cache it now
        if apicaches.count() == 0:
            apicache = APICache(
                url=url,
                parameters=params_repr,
                cached_until = times['until'],
                text = data,
            )
            apicache.save()
        
        return (root, times)

# ---------------------------------------------------------------------------
# Turn an API date into a datetime object
def parse_api_date(s):
    return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')

# ---------------------------------------------------------------------------
# Spit out an error message
def show_error(text, err, times):
    print '(%s) %s: %s | %s -> %s' % (text, err.attrib['code'], err.text, times['current'], times['until'])

# ---------------------------------------------------------------------------
# Caching item fetcher
_item_cache = {}
def get_item(item_id):
    if item_id not in _item_cache:
        _item_cache[item_id] = Item.objects.get(pk=item_id)
    return _item_cache[item_id]

# ---------------------------------------------------------------------------
# Caching corporation fetcher, adds new corporations to the database
_corp_cache = {}
def get_corporation(corp_id, corp_name):
    if corp_id not in _corp_cache:
        corps = Corporation.objects.filter(pk=corp_id)
        # Corporation already exists
        if corps.count() > 0:
            corp = corps[0]
        # Corporation doesn't exist, make a new object and save it
        else:
            corp = Corporation(id=corp_id, name=corp_name)
            corp.save()
        
        _corp_cache[corp_id] = corp
    
    return _corp_cache[corp_id]

# ---------------------------------------------------------------------------
# Caching station fetcher, adds unknown stations to the database
_station_cache = {}
def get_station(station_id, station_name):
    if station_id not in _station_cache:
        stations = Station.objects.filter(pk=station_id)
        # Station already exists
        if stations.count() > 0:
            station = stations[0]
        # Station doesn't exist, make a new object and save it
        else:
            station = Station(id=station_id, name=station_name)
            station.save()
        
        _station_cache[station_id] = station

    # Update the station name if it has changed since we last saw it
    if _station_cache[station_id].name != station_name and station_name != 'UNKNOWN STATION':
        _station_cache[station_id].name = station_name
        _station_cache[station_id].save()
    
    return _station_cache[station_id]

# ---------------------------------------------------------------------------

if __name__ == '__main__':
    updater = APIUpdater(True)
    updater.go()
