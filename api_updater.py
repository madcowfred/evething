#!/usr/local/bin/python

import datetime
import logging
import os
import requests
import sys
import threading
import time
try:
    import xml.etree.cElementTree as ET
except:
    import xml.etree.ElementTree as ET

from Queue import Queue
from collections import OrderedDict
from decimal import *

# Aurgh
from django.core.management import setup_environ
from evething import settings
setup_environ(settings)

from django.core.urlresolvers import reverse
from django.db import connection

from thing.models import *


# base headers
HEADERS = {
    'User-Agent': 'EVEthing-api-updater',
}

# my API proxy, you should probably either run your own or uncomment the second line
BASE_URL = 'http://proxy.evething.org'
#BASE_URL = 'http://api.eveonline.com'

ACCOUNT_INFO_URL = '%s/account/AccountStatus.xml.aspx' % (BASE_URL)
API_INFO_URL = '%s/account/APIKeyInfo.xml.aspx' % (BASE_URL)
ASSETS_CHAR_URL = '%s/char/AssetList.xml.aspx' % (BASE_URL)
ASSETS_CORP_URL = '%s/corp/AssetList.xml.aspx' % (BASE_URL)
BALANCE_URL = '%s/corp/AccountBalance.xml.aspx' % (BASE_URL)
CHAR_SHEET_URL = '%s/char/CharacterSheet.xml.aspx' % (BASE_URL)
CORP_SHEET_URL = '%s/corp/CorporationSheet.xml.aspx' % (BASE_URL)
LOCATIONS_CHAR_URL = '%s/char/Locations.xml.aspx' % (BASE_URL)
ORDERS_CHAR_URL = '%s/char/MarketOrders.xml.aspx' % (BASE_URL)
ORDERS_CORP_URL = '%s/corp/MarketOrders.xml.aspx' % (BASE_URL)
SKILL_QUEUE_URL = '%s/char/SkillQueue.xml.aspx' % (BASE_URL)
TRANSACTIONS_CHAR_URL = '%s/char/WalletTransactions.xml.aspx' % (BASE_URL)
TRANSACTIONS_CORP_URL = '%s/corp/WalletTransactions.xml.aspx' % (BASE_URL)

# ---------------------------------------------------------------------------
# Simple job-consuming worker thread
class APIWorker(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)

        self.queue = queue

    def run(self):
        logging.info('%s: started', self.name)
        while True:
            job = self.queue.get()
            # die die die
            if job is None:
                self.queue.task_done()
                return
            else:
                try:
                    job.run()
                except:
                    logging.error('Trapped exception!', exc_info=sys.exc_info())

                self.queue.task_done()

# ---------------------------------------------------------------------------

class APIJob:
    def __init__(self, apikey, character=None):
        self._apikey = apikey
        self._character = character
    
    # ---------------------------------------------------------------------------
    # Perform an API request and parse the returned XML via ElementTree
    def fetch_api(self, url, params):
        start = time.time()

        # Add the API key information
        params['keyID'] = self._apikey.id
        params['vCode'] = self._apikey.vcode

        # Check the API cache for this URL/params combo
        now = datetime.datetime.utcnow()
        params_repr = repr(sorted(params.items()))
        
        try:
            apicache = APICache.objects.get(url=url, parameters=params_repr, cached_until__gt=now)

        # Data is not cached, fetch new data
        except APICache.DoesNotExist:
            apicache = None
            
            logging.info('Fetching URL %s', url)

            # Fetch the URL
            r = requests.post(url, params, headers=HEADERS, config={ 'max_retries': 1 })
            data = r.text
            
            logging.info('URL retrieved in %s', datetime.datetime.utcnow() - now)

            # If the status code is bad return None
            if not r.status_code == requests.codes.ok:
                #self._total_api += (time.time() - start)
                return (None, {}, None)

        # Data is cached, use that
        else:
            logging.info('Cached URL %s', url)
            data = apicache.text

        # Parse the XML
        root = ET.fromstring(data)
        times = {
            'current': parse_api_date(root.find('currentTime').text),
            'until': parse_api_date(root.find('cachedUntil').text),
        }
        
        # If the data wasn't cached, cache it now
        if apicache is None:
            apicache = APICache(
                url=url,
                parameters=params_repr,
                cached_until=times['until'],
                text=data,
                completed_ok=False,
            )
            apicache.save()
        
        #self._total_api += (time.time() - start)

        return (root, times, apicache)

# ---------------------------------------------------------------------------
# Do various API key things
class APICheck(APIJob):
    def run(self):
        root, times, apicache = self.fetch_api(API_INFO_URL, {})
        if root is None:
            #show_error('api_check', 'HTTP error', times)
            return

        # cached and completed ok? pass.
        if apicache and apicache.completed_ok:
            return
        
        # Check for errors
        err = root.find('error')
        if err is not None:
            # 202/203/204/205/210/212 Authentication failure
            # 207 Not available for NPC corporations
            # 220 Invalid corporate key
            # 222 Key has expired
            # 223 Legacy API key
            if err.attrib['code'] in ('202', '203', '204', '205', '210', '212', '207', '220', '222', '223'):
                self._apikey.valid = False
                self._apikey.save()

            return
        
        # Find the key node
        key_node = root.find('result/key')
        # Update access mask
        self._apikey.access_mask = int(key_node.attrib['accessMask'])
        # Update expiry date
        expires = key_node.attrib['expires']
        if expires:
            self._apikey.expires = parse_api_date(expires)
        # Update key type
        self._apikey.key_type = key_node.attrib['type']
        # Save
        self._apikey.save()
        
        # Handle character key type keys
        if key_node.attrib['type'] in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
            seen_chars = []
            
            for row in key_node.findall('rowset/row'):
                characterID = row.attrib['characterID']
                seen_chars.append(characterID)
                
                # Get a corporation object
                corp = get_corporation(row.attrib['corporationID'], row.attrib['corporationName'])
                
                characters = Character.objects.filter(id=characterID)
                # Character doesn't exist, make a new one and save it
                if characters.count() == 0:
                    character = Character(
                        id=characterID,
                        apikey=self._apikey,
                        name=row.attrib['characterName'],
                        corporation=corp,
                        wallet_balance=0,
                        cha_attribute=0,
                        cha_bonus=0,
                        int_attribute=0,
                        int_bonus=0,
                        mem_attribute=0,
                        mem_bonus=0,
                        per_attribute=0,
                        per_bonus=0,
                        wil_attribute=0,
                        wil_bonus=0,
                        clone_name='',
                        clone_skill_points=0,
                    )
                # Character exists, update API key and corporation information
                else:
                    character = characters[0]
                    character.apikey = self._apikey
                    character.corporation = corp
                
                # Save the character
                character.save()
            
            # Unlink any characters that are no longer valid for this API key
            for character in Character.objects.filter(apikey=self._apikey).exclude(pk__in=seen_chars):
                character.apikey = None
                character.save()
        
        # Handle corporate key
        elif key_node.attrib['type'] == APIKey.CORPORATION_TYPE:
            row = key_node.find('rowset/row')
            characterID = row.attrib['characterID']
            
            # Get a corporation object
            corp = get_corporation(row.attrib['corporationID'], row.attrib['corporationName'])
            
            characters = Character.objects.filter(id=characterID)
            # Character doesn't exist, make a new one and save it
            if characters.count() == 0:
                character = Character(
                    id=characterID,
                    name=row.attrib['characterName'],
                    corporation=corp,
                )
            else:
                character = characters[0]
            
            self._apikey.corp_character = character
            self._apikey.save()

        # completed ok
        apicache.completed_ok = True
        apicache.save()

# ---------------------------------------------------------------------------
# Fetch account status
class AccountStatus(APIJob):
    def run(self):
        # Don't check corporate keys
        if self._apikey.corp_character:
            return

        # Make sure the access mask matches
        if (self._apikey.access_mask & 33554432) == 0:
            return

        # Fetch the API data
        root, times, apicache = self.fetch_api(ACCOUNT_INFO_URL, {})
        if root is None:
            #show_error('fetch_account_status', 'HTTP error', times)
            return
        
        # cached and completed ok? pass.
        if apicache and apicache.completed_ok:
            return
        
        err = root.find('error')
        if err is not None:
            show_error('fetch_account_status', err, times)
            return

        # Update paid_until
        self._apikey.paid_until = parse_api_date(root.findtext('result/paidUntil'))

        self._apikey.save()
        
        # completed ok
        apicache.completed_ok = True
        apicache.save()

# ---------------------------------------------------------------------------
class Assets(APIJob):
    def run(self):
        # Initialise for corporate query
        if self._apikey.corp_character:
            mask = 2
            url = ASSETS_CORP_URL
            a_filter = Asset.objects.filter(corporation=self._apikey.corp_character.corporation)
        # Initialise for character query
        else:
            mask = 2
            url = ASSETS_CHAR_URL
            a_filter = Asset.objects.filter(character=self._character, corporation__isnull=True)

        # Make sure the access mask matches
        if (self._apikey.access_mask & mask) == 0:
            return

        # Fetch the API data
        params = { 'characterID': self._character.id }
        root, times, apicache = self.fetch_api(url, params)
        if root is None:
            #show_error('fetch_assets', 'HTTP error', times)
            return
        
        # cached and completed ok? pass.
        if apicache and apicache.completed_ok:
            return
        
        err = root.find('error')
        if err is not None:
            show_error('fetch_assets', err, times)
            return

        #if self._apikey.corp_character:
        #    open('assets.xml', 'w').write(ET.tostring(root))
        #    return

        # Generate an asset_id map
        asset_ids = set()
        asset_map = {}
        for asset in a_filter:
            asset_map[asset.id] = asset

        # ACTIVATE RECURSION :siren:
        rows = {}
        self.assets_recurse(rows, root.find('result/rowset'), None)

        # assetID - [0]system, [1]station, [2]container_id, [3]item, [4]flag, [5]quantiy, [6]rawQuantity, [7]singleton
        errors = 0
        while rows:
            assets = list(rows.items())
            
            for id, data in assets:
                # asset has a container_id...
                if data[2] is not None:
                    # and the container_id doesn't exist, yet we have to do this later
                    try:
                        parent = Asset.objects.get(pk=data[2])
                    except Asset.DoesNotExist:
                        continue
                # asset has no container_id
                else:
                    parent = None

                create = False

                # if the asset already exists and has changed, delete it and create a new one
                asset = asset_map.get(id, None)
                if asset is not None:
                    if asset.system != data[0] or asset.station != data[1] or asset.parent != parent or \
                       asset.item != data[3] or asset.inv_flag_id != data[4] or asset.quantity != data[5] or \
                       asset.raw_quantity != data[6] or asset.singleton != data[7]:

                        asset.delete()
                        create = True
                # doesn't exist, create a new one
                else:
                    create = True

                if create is True:
                    #print 'create!'
                    asset = Asset(
                        id=id,
                        character=self._character,
                        system=data[0],
                        station=data[1],
                        parent=parent,
                        item=data[3],
                        inv_flag_id=data[4],
                        quantity=data[5],
                        raw_quantity=data[6],
                        singleton=data[7],
                    )
                    if self._apikey.corp_character:
                        asset.corporation = self._apikey.corp_character.corporation
                    asset.save()

                    asset_map[id] = asset

                asset_ids.add(id)
                del rows[id]

        # Delete any assets that we didn't see now
        a_filter.exclude(pk__in=asset_ids).delete()

        # completed ok
        apicache.completed_ok = True
        apicache.save()

    # Recursively visit the assets tree and gather data
    def assets_recurse(self, rows, rowset, container_id):
        for row in rowset.findall('row'):
            # No container_id (parent)
            if 'locationID' in row.attrib:
                location_id = int(row.attrib['locationID'])

                # :ccp: as fuck
                # http://wiki.eve-id.net/APIv2_Corp_AssetList_XML#officeID_to_stationID_conversion
                if 66000000 <= location_id <= 66014933:
                    location_id -= 6000001
                elif 66014934 <= location_id <= 67999999:
                    location_id -= 6000000

                system = get_system(location_id)
                station = get_station(location_id)
            else:
                system = None
                station = None

            try:
                item = get_item(row.attrib['typeID'])
            except Item.DoesNotExist:
                logging.warn("Item #%s apparently doesn't exist", row.attrib['typeID'])
                continue

            asset_id = int(row.attrib['itemID'])
            rows[asset_id] = [
                system,
                station,
                container_id,
                item,
                int(row.attrib['flag']),
                int(row.attrib.get('quantity', '0')),
                int(row.attrib.get('rawQuantity', '0')),
                int(row.attrib.get('singleton', '0')),
            ]

            # Now we need to visit children rowsets
            for rowset in row.findall('rowset'):
                self.assets_recurse(rows, rowset, asset_id)

# ---------------------------------------------------------------------------
# Fetch and add/update character sheet data
class CharacterSheet(APIJob):
    def run(self):
        # Make sure the access mask matches
        if (self._apikey.access_mask & 8) == 0:
            return
        
        # Fetch the API data
        params = { 'characterID': self._character.id }
        root, times, apicache = self.fetch_api(CHAR_SHEET_URL, params)
        if root is None:
            #show_error('fetch_char_sheet', 'HTTP error', times)
            return
        
        # cached and completed ok? pass.
        if apicache and apicache.completed_ok:
            return
        
        err = root.find('error')
        if err is not None:
            show_error('fetch_char_sheet', err, times)
            return
        
        # Update wallet balance
        self._character.wallet_balance = root.findtext('result/balance')
        
        # Update attributes
        self._character.cha_attribute = root.findtext('result/attributes/charisma')
        self._character.int_attribute = root.findtext('result/attributes/intelligence')
        self._character.mem_attribute = root.findtext('result/attributes/memory')
        self._character.per_attribute = root.findtext('result/attributes/perception')
        self._character.wil_attribute = root.findtext('result/attributes/willpower')
        
        # Update attribute bonuses :ccp:
        enh = root.find('result/attributeEnhancers')

        val = enh.find('charismaBonus/augmentatorValue')
        if val is None:
            self._character.cha_bonus = 0
        else:
            self._character.cha_bonus = val.text

        val = enh.find('intelligenceBonus/augmentatorValue')
        if val is None:
            self._character.int_bonus = 0
        else:
            self._character.int_bonus = val.text

        val = enh.find('memoryBonus/augmentatorValue')
        if val is None:
            self._character.mem_bonus = 0
        else:
            self._character.mem_bonus = val.text

        val = enh.find('perceptionBonus/augmentatorValue')
        if val is None:
            self._character.per_bonus = 0
        else:
            self._character.per_bonus = val.text

        val = enh.find('willpowerBonus/augmentatorValue')
        if val is None:
            self._character.wil_bonus = 0
        else:
            self._character.wil_bonus = val.text

        # Update clone information
        self._character.clone_skill_points = root.findtext('result/cloneSkillPoints')
        self._character.clone_name = root.findtext('result/cloneName')

        # Get all of the rowsets
        rowsets = root.findall('result/rowset')
        
        # First rowset is skills
        skills = {}
        for row in rowsets[0]:
            skills[int(row.attrib['typeID'])] = (int(row.attrib['skillpoints']), int(row.attrib['level']))
        
        # Grab any already existing skills
        for char_skill in CharacterSkill.objects.select_related('item', 'skill').filter(character=self._character, skill__in=skills.keys()):
            points, level = skills[char_skill.skill.item_id]
            if char_skill.points != points or char_skill.level != level:
                char_skill.points = points
                char_skill.level = level
                char_skill.save()
            
            del skills[char_skill.skill.item_id]
        
        # Add any leftovers
        for skill_id, (points, level) in skills.items():
            char_skill = CharacterSkill(
                character=self._character,
                skill_id=skill_id,
                points=points,
                level=level,
            )
            char_skill.save()
        
        # Save character
        self._character.save()
        
        # completed ok
        apicache.completed_ok = True
        apicache.save()

# ---------------------------------------------------------------------------
# Fetch and add/update character skill queue
class CharacterSkillQueue(APIJob):
    def run(self):
        # Make sure the access mask matches
        if (self._apikey.access_mask & 262144) == 0:
            return
        
        # Fetch the API data
        params = { 'characterID': self._character.id }
        root, times, apicache = self.fetch_api(SKILL_QUEUE_URL, params)
        if root is None:
            #show_error('fetch_char_skill_queue', 'HTTP error', times)
            return
        
        # cached and completed ok? pass.
        if apicache and apicache.completed_ok:
            return
        
        err = root.find('error')
        if err is not None:
            show_error('fetch_char_skill_queue', err, times)
            return
        
        # Delete the old queue
        SkillQueue.objects.filter(character=self._character).delete()
        
        # Add new skills
        for row in root.findall('result/rowset/row'):
            if row.attrib['startTime'] and row.attrib['endTime']:
                sq = SkillQueue(
                    character=self._character,
                    skill_id=row.attrib['typeID'],
                    start_time=row.attrib['startTime'],
                    end_time=row.attrib['endTime'],
                    start_sp=row.attrib['startSP'],
                    end_sp=row.attrib['endSP'],
                    to_level=row.attrib['level'],
                )
                sq.save()
        
        # completed ok
        apicache.completed_ok = True
        apicache.save()

# ---------------------------------------------------------------------------
# Fetch corporation sheet
class CorporationSheet(APIJob):
    def run(self):
        # Make sure the access mask matches
        if (self._apikey.access_mask & 8) == 0:
            return
        
        params = { 'characterID': self._apikey.corp_character_id }
        
        root, times, apicache = self.fetch_api(CORP_SHEET_URL, params)
        if root is None:
            #show_error('fetch_corp_sheet', 'HTTP error', times)
            return
        
        # cached and completed ok? pass.
        if apicache and apicache.completed_ok:
            return
        
        err = root.find('error')
        if err is not None:
            show_error('fetch_corp_sheet', err, times)
            return
        
        corporation = self._apikey.corp_character.corporation
        
        ticker = root.find('result/ticker')
        corporation.ticker = ticker.text
        corporation.save()
        
        errors = 0
        for rowset in root.findall('result/rowset'):
            if rowset.attrib['name'] == 'divisions':
                rows = rowset.findall('row')

                corporation.division1 = rows[0].attrib['description']
                corporation.division2 = rows[1].attrib['description']
                corporation.division3 = rows[2].attrib['description']
                corporation.division4 = rows[3].attrib['description']
                corporation.division5 = rows[4].attrib['description']
                corporation.division6 = rows[5].attrib['description']
                corporation.division7 = rows[6].attrib['description']
                corporation.save()

            if rowset.attrib['name'] == 'walletDivisions':
                wallet_map = {}
                for cw in CorpWallet.objects.filter(corporation=corporation):
                    wallet_map[cw.account_key] = cw
                
                for row in rowset.findall('row'):
                    wallet = wallet_map.get(int(row.attrib['accountKey']), None)
                    # If the wallet exists, update the description
                    if wallet is not None:
                        if wallet.description != row.attrib['description']:
                            wallet.description = row.attrib['description']
                            wallet.save()
                    # If it doesn't exist, wtf?
                    else:
                        logging.warn("No matching CorpWallet object for corpID=%s accountkey=%s", corporation.id, row.attrib['accountKey'])
                        errors += 1
        
        # completed ok
        if errors == 0:
            apicache.completed_ok = True
            apicache.save()

# ---------------------------------------------------------------------------
# Fetch corporation wallets
class CorporationWallets(APIJob):
    def run(self):
        # Make sure the access mask matches
        if (self._apikey.access_mask & 1) == 0:
            return
        
        params = { 'characterID': self._apikey.corp_character_id }
        
        root, times, apicache = self.fetch_api(BALANCE_URL, params)
        if root is None:
            #show_error('fetch_corp_wallets', 'HTTP error', times)
            return
        
        # cached and completed ok? pass.
        if apicache and apicache.completed_ok:
            return
        
        err = root.find('error')
        if err is not None:
            show_error('fetch_corp_wallets', err, times)
            return
        
        corporation = self._apikey.corp_character.corporation
        wallet_map = {}
        for cw in CorpWallet.objects.filter(corporation=corporation):
            wallet_map[cw.account_key] = cw
        
        for row in root.findall('result/rowset/row'):
            accountID = int(row.attrib['accountID'])
            accountKey = int(row.attrib['accountKey'])
            balance = Decimal(row.attrib['balance'])
            
            wallet = wallet_map.get(accountKey, None)
            # If the wallet exists, update the balance
            if wallet is not None:
                if balance != wallet.balance:
                    wallet.balance = balance
                    wallet.save()
            # Otherwise just make a new one
            else:
                wallet = CorpWallet(
                    account_id=accountID,
                    corporation=corporation,
                    account_key=accountKey,
                    description='',
                    balance=balance,
                )
                wallet.save()
        
        # completed ok
        apicache.completed_ok = True
        apicache.save()

# ---------------------------------------------------------------------------
# Fetch locations (and more importantly names) for assets
class Locations(APIJob):
    def run(self):
        # Initialise for character query
        if not self._apikey.corp_character:
            mask = 134217728
            url = LOCATIONS_CHAR_URL
            a_filter = Asset.objects.root_nodes().filter(character=self._character, corporation__isnull=True, singleton=True, item__item_group__category__name__in=('Celestial', 'Ship'))

        # Make sure the access mask matches
        if (self._apikey.access_mask & mask) == 0:
            return

        # Get ID list
        ids = map(str, a_filter.values_list('id', flat=True))
        if len(ids) == 0:
            return

        # Fetch the API data
        params = {
            'characterID': self._character.id,
            'IDs': ','.join(map(str, a_filter.values_list('id', flat=True))),
        }
        root, times, apicache = self.fetch_api(url, params)
        if root is None:
            #show_error('fetch_asset_locations', 'HTTP error', times)
            return
        
        # cached and completed ok? pass.
        if apicache and apicache.completed_ok:
            return
        
        err = root.find('error')
        if err is not None:
            show_error('fetch_asset_locations', err, times)
            return

        #open('locations.xml', 'w').write(ET.tostring(root))

        for row in root.findall('result/rowset/row'):
            ca = Asset.objects.get(character=self._character, id=row.attrib['itemID'])
            if ca.name is None or ca.name != row.attrib['itemName']:
                #print 'changing name to %r (%d)' % (row.attrib['itemName'], len(row.attrib['itemName']))
                ca.name = row.attrib['itemName']
                ca.save()
        
        # completed ok
        apicache.completed_ok = True
        apicache.save()

# ---------------------------------------------------------------------------
# Fetch and add/update market orders
class MarketOrders(APIJob):
    def run(self):
        # Generate a character id map
        self.char_id_map = {}
        for character in Character.objects.all():
            self.char_id_map[character.id] = character


        # Initialise for corporate query
        if self._apikey.corp_character:
            mask = 4096
            url = ORDERS_CORP_URL
            o_filter = MarketOrder.objects.filter(corp_wallet__corporation=self._character.corporation)
            
            wallet_map = {}
            for cw in CorpWallet.objects.filter(corporation=self._character.corporation):
                wallet_map[cw.account_key] = cw
        
        # Initialise for character query
        else:
            mask = 4096
            url = ORDERS_CHAR_URL
            o_filter = MarketOrder.objects.filter(corp_wallet=None, character=self._character)
        
        # Make sure the access mask matches
        if (self._apikey.access_mask & mask) == 0:
            return
        
        # Fetch the API data
        params = { 'characterID': self._character.id }
        root, times, apicache = self.fetch_api(url, params)
        if root is None:
            #show_error('fetch_orders', 'HTTP error', times)
            return
        
        # cached and completed ok? pass.
        if apicache and apicache.completed_ok:
            return
        
        err = root.find('error')
        if err is not None:
            show_error('fetch_orders', err, times)
            return
        
        # Generate an order_id map
        order_map = {}
        for mo in o_filter.select_related('item'):
            order_map[mo.order_id] = mo
        
        # Iterate over the returned result set
        seen = []
        for row in root.findall('result/rowset/row'):
            order_id = int(row.attrib['orderID'])
            #orders = MarketOrder.objects.filter(order_id=order_id, character=character)
            
            # Order exists
            order = order_map.get(order_id, None)
            if order is not None:
                # Order is still active, update relevant details
                if row.attrib['orderState'] == '0':
                    issued = parse_api_date(row.attrib['issued'])
                    volRemaining = int(row.attrib['volRemaining'])
                    escrow = Decimal(row.attrib['escrow'])
                    price = Decimal(row.attrib['price'])

                    if issued > order.issued or \
                       volRemaining != order.volume_remaining or \
                       escrow != order.escrow or \
                       price != order.price:
                        order.issued = parse_api_date(row.attrib['issued'])
                        order.volume_remaining = int(row.attrib['volRemaining'])
                        order.escrow = Decimal(row.attrib['escrow'])
                        order.price = Decimal(row.attrib['price'])
                        order.total_price = order.volume_remaining * order.price
                        order.save()
                    
                    seen.append(order_id)
                
                # Not active, delete order
                #else:
                #    order.delete()
            
            # Doesn't exist and is active, make a new order
            elif row.attrib['orderState'] == '0':
                if row.attrib['bid'] == '0':
                    buy_order = False
                else:
                    buy_order = True
                
                # Make sure the character charID is valid
                char = self.char_id_map.get(int(row.attrib['charID']))
                if char is None:
                    logging.warn("No matching Character object for charID=%s", row.attrib['charID'])
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
                issued = parse_api_date(row.attrib['issued'])
                order = MarketOrder(
                    order_id=order_id,
                    station=get_station(int(row.attrib['stationID'])),
                    item=get_item(row.attrib['typeID']),
                    character=char,
                    escrow=Decimal(row.attrib['escrow']),
                    price=price,
                    total_price=remaining * price,
                    buy_order=buy_order,
                    volume_entered=int(row.attrib['volEntered']),
                    volume_remaining=remaining,
                    minimum_volume=int(row.attrib['minVolume']),
                    issued=issued,
                    expires=issued + datetime.timedelta(int(row.attrib['duration'])),
                )
                # Set the corp_wallet for corporation API requests
                if self._apikey.corp_character:
                    #order.corp_wallet = CorpWallet.objects.get(corporation=character.corporation, account_key=row.attrib['accountKey'])
                    order.corp_wallet = wallet_map.get(int(row.attrib['accountKey']))
                order.save()
                
                seen.append(order_id)
        

        # Any orders we didn't see need to be deleted - issue events first
        to_delete = o_filter.exclude(pk__in=seen)
        now = datetime.datetime.now()
        for order in to_delete.select_related():
            if order.buy_order:
                buy_sell = 'buy'
            else:
                buy_sell = 'sell'
            if order.corp_wallet:
                order_type = 'corporate'
            else:
                order_type = 'personal'

            url = reverse('transactions-all', args=[order.item.id, 'all'])
            text = '%s: %s %s order for <a href="%s">%s</a> completed/expired (%s)' % (order.station.short_name, order_type, buy_sell, url, 
                order.item.name, order.character.name)

            event = Event(
                user_id=self._apikey.user.id,
                issued=now,
                text=text,
            )
            event.save()

        # Then delete
        to_delete.delete()
        
        # completed ok
        apicache.completed_ok = True
        apicache.save()

# ---------------------------------------------------------------------------
# Fetch wallet transactions
class WalletTransactions(APIJob):
    def run(self):
        # Generate a character id map
        self.char_id_map = {}
        for character in Character.objects.all():
            self.char_id_map[character.id] = character


        # Initialise stuff
        params = { 'characterID': self._character.id }
        
        # Corporate key
        if self._apikey.corp_character:
            params['accountKey'] = self._corp_wallet.account_key
            mask = 2097152
            url = TRANSACTIONS_CORP_URL
            t_filter = Transaction.objects.filter(corp_wallet__corporation=self._character.corporation)
        # Character key
        else:
            mask = 4194304
            url = TRANSACTIONS_CHAR_URL
            t_filter = Transaction.objects.filter(corp_wallet=None, character=self._character)
        
        # Make sure the access mask matches
        if (self._apikey.access_mask & mask) == 0:
            return
        
        # Loop until we run out of transactions
        errors = 0
        one_week_ago = None
        while True:
            root, times, apicache = self.fetch_api(url, params)
            if root is None:
                #show_error('fetch_transactions', 'HTTP error', times)
                return

            # cached and completed ok? pass.
            if apicache and apicache.completed_ok:
                return

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
            
            # Make a transaction id:row map
            t_map = OrderedDict()
            for row in rows:
                transaction_id = int(row.attrib['transactionID'])
                transaction_time = parse_api_date(row.attrib['transactionDateTime'])
                t_map[transaction_id] = (transaction_time, row)
            
            # Query those transaction ids and delete any we've already seen
            for trans in t_filter.filter(transaction_id__in=t_map.keys()):
                if trans.transaction_id in t_map:
                    del t_map[trans.transaction_id]
                else:
                    logging.warn("transaction_id not in t_map, what in the fuck?")
                    errors += 1
            
            # Now iterate over the leftovers
            for transaction_id, (transaction_time, row) in t_map.items():
                # Initalise some variables
                #transaction_time = parse_api_date(row.attrib['transactionDateTime'])
                
                # Skip corporate transactions if this is a personal call, we have no idea
                # what wallet this transaction is related to otherwise :ccp:
                if not self._apikey.corp_character and row.attrib['transactionFor'] == 'corporation':
                    continue
                
                # Check to see if this transaction already exists
                #if transactions.filter(transaction_id=transaction_id, date=transaction_time).count():
                #    continue
                
                # Make sure the item typeID is valid
                #items = Item.objects.filter(pk=row.attrib['typeID'])
                #if items.count() == 0:
                #    print "ERROR: item with typeID '%s' does not exist, what the fuck?" % (row.attrib['typeID'])
                #    print '>> attrib = %r' % (row.attrib)
                #    continue
                
                # Make the station object if it doesn't already exist
                station = get_station(int(row.attrib['stationID']))
                
                # Work out what the character should be
                if self._apikey.corp_character:
                    try:
                        char = self.char_id_map[int(row.attrib['characterID'])]
                    except KeyError:
                        print repr(row.attrib)
                        raise
                else:
                    char = self._character
                
                # Create a new transaction object and save it
                quantity = int(row.attrib['quantity'])
                price = Decimal(row.attrib['price'])
                buy_transaction = (row.attrib['transactionType'] == 'buy')

                try:
                    item = get_item(row.attrib['typeID'])
                except Item.DoesNotExist:
                    logging.warn("Item #%s apparently doesn't exist", row.attrib['typeID'])
                    errors += 1
                    continue

                t = Transaction(
                    station=station,
                    character=char,
                    item=get_item(row.attrib['typeID']),
                    transaction_id=transaction_id,
                    date=transaction_time,
                    buy_transaction=buy_transaction,
                    quantity=quantity,
                    price=price,
                    total_price=quantity * price,
                )
                # Set the corp_character for corporation API requests
                if self._apikey.corp_character:
                    t.corp_wallet = self._corp_wallet
                t.save()
            
            # If we got 1000 rows we should retrieve some more
            #print 'DEBUG: rows: %d | cur: %s | owa: %s | tt: %s' % (len(rows), times['current'], one_week_ago, transaction_time)
            if len(rows) == 1000 and transaction_time > one_week_ago:
                params['beforeTransID'] = transaction_id
            else:
                break
        
        # completed ok
        if errors == 0:
            apicache.completed_ok = True
            apicache.save()

# ---------------------------------------------------------------------------

class APIUpdater:
    def __init__(self):
        #self._total_api = 0

        # do a dummy strptime because strptime is not fucking thread safe?
        datetime.datetime.strptime('2012-01-01', '%Y-%m-%d')

        # set up logging
        if settings.DEBUG:
            level = logging.INFO
        else:
            level = logging.WARNING
        logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=level)

        # job queue
        self._job_queue = Queue()

        # start our thread pool
        self._threads = []
        for i in range(4):
            t = APIWorker(self._job_queue)
            t.start()
            self._threads.append(t)

    def stop_threads(self):
        for t in self._threads:
            self._job_queue.put(None)

        self._job_queue.join()

    def go(self):
        # Make sure API keys are valid first
        for apikey in APIKey.objects.select_related().filter(valid=True).order_by('key_type'):
            job = APICheck(apikey)
            self._job_queue.put(job)

        # Wait for all key checks to be completed
        self._job_queue.join()

        # Now we can get down to business
        for apikey in APIKey.objects.filter(valid=True, access_mask__isnull=False):
            # Make sure account status is up to date
            job = AccountStatus(apikey)
            self._job_queue.put(job)

            # Account/Character key are basically the same thing
            if apikey.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
                for character in apikey.character_set.all():
                    # Fetch character sheet
                    job = CharacterSheet(apikey, character)
                    self._job_queue.put(job)

                    # Fetch character skill queue
                    job = CharacterSkillQueue(apikey, character)
                    self._job_queue.put(job)
                    
                    # Fetch market orders
                    job = MarketOrders(apikey, character)
                    self._job_queue.put(job)
                    
                    # Fetch wallet transactions
                    job = WalletTransactions(apikey, character)
                    self._job_queue.put(job)
                    
                    # Fetch assets
                    job = Assets(apikey, character)
                    self._job_queue.put(job)

                    # Fetch asset locations
                    job = Locations(apikey, character)
                    self._job_queue.put(job)

            # Corporation key
            elif apikey.key_type == APIKey.CORPORATION_TYPE:
                character = apikey.corp_character
                if character is None:
                    logging.warn('API key %s is a corporation key with null corp_character!', apikey.id)
                    continue
                corporation = character.corporation
                
                # Update wallet information first
                job = CorporationWallets(apikey)
                self._job_queue.put(job)
                
                # Update corporation sheet information (wallet division names mostly)
                job = CorporationSheet(apikey)
                self._job_queue.put(job)

                # Fetch market orders
                job = MarketOrders(apikey, character)
                self._job_queue.put(job)

                # Fetch wallet transactions
                for corp_wallet in CorpWallet.objects.filter(corporation=corporation):
                    job = WalletTransactions(apikey, character)
                    job._corp_wallet = corp_wallet
                    self._job_queue.put(job)

                # Fetch assets
                job = Assets(apikey, character)
                self._job_queue.put(job)

        # All done, shut down the threads
        self.stop_threads()

    # -----------------------------------------------------------------------
    # Do the heavy lifting
    def old_go(self):
        start = time.time()


        # All done, clean up any out-of-date cached API requests
        now = datetime.datetime.utcnow()
        APICache.objects.filter(cached_until__lt=now).delete()
        
        # And dump some debug info
        if self.debug:
            debug = open('/tmp/api.debug', 'w')
            debug.write('%.3fs  %d queries (%.3fs)  API: %.1fs\n\n' % (time.time() - start,
                len(connection.queries), sum(float(q['time']) for q in connection.queries),
                self._total_api))
            debug.write('\n')
            for query in connection.queries:
               debug.write('%02.3fs  %s\n' % (float(query['time']), query['sql']))
            debug.close()
    
    # -----------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Turn an API date into a datetime object
_pad_lock = threading.Lock()
def parse_api_date(s):
    with _pad_lock:
        return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')

# ---------------------------------------------------------------------------
# Spit out an error message
def show_error(func, err, times):
    current = times.get('current', '?')
    until = times.get('until', '?')

    # Stupid OUR SERVER IS FUCKED AGAIN errors
    # 520 Unexpected failure accessing database
    # 901 Web site database temporarily disabled
    # 902 EVE backend database temporarily disabled
    if 'Scotty the docking manager' in err.text or err.attrib['code'] in ('520', '901', '902'):
        return

    if hasattr(err, 'attrib'):
        logging.error('(%s) %s: %s | %s -> %s', func, err.attrib['code'], err.text, current, until)
    else:
        logging.error('(%s) %s | %s -> %s', func, err, current, until)

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
# Caching system fetcher
_system_cache = {}
def get_system(system_id):
    if system_id not in _system_cache:
        try:
            system = System.objects.get(pk=system_id)
        except System.DoesNotExist:
            system = None
        
        _system_cache[system_id] = system
    
    return _system_cache[system_id]

# ---------------------------------------------------------------------------
# Caching station fetcher
_station_cache = {}
def get_station(station_id):
    if station_id not in _station_cache:
        try:
            station = Station.objects.get(pk=station_id)
        except Station.DoesNotExist:
            station = None
        
        _station_cache[station_id] = station
    
    return _station_cache[station_id]

# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # don't start if the lock file exists
    lockfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api.lock')
    if os.path.isfile(lockfile):
        sys.exit(0)

    open(lockfile, 'w').write(str(os.getpid()))

    updater = APIUpdater()
    updater.go()

    os.remove(lockfile)
