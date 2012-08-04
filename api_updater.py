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
from urlparse import urljoin

# Aurgh
os.environ['DJANGO_SETTINGS_MODULE'] = 'evething.settings'
from django.conf import settings

from django.core.urlresolvers import reverse
from django.db import connection, transaction, IntegrityError

from thing.models import *
from thing import queries


# base headers
HEADERS = {
    'User-Agent': 'EVEthing-api-updater',
}

ACCOUNT_INFO_URL = '/account/AccountStatus.xml.aspx'
API_INFO_URL = '/account/APIKeyInfo.xml.aspx'
ASSETS_CHAR_URL = '/char/AssetList.xml.aspx'
ASSETS_CORP_URL = '/corp/AssetList.xml.aspx'
BALANCE_URL = '/corp/AccountBalance.xml.aspx'
CHAR_NAME_URL = '/eve/CharacterName.xml.aspx'
CHAR_SHEET_URL = '/char/CharacterSheet.xml.aspx'
CONTRACTS_CHAR_URL = '/char/Contracts.xml.aspx'
CONTRACTS_CORP_URL = '/corp/Contracts.xml.aspx'
CORP_SHEET_URL = '/corp/CorporationSheet.xml.aspx'
LOCATIONS_CHAR_URL = '/char/Locations.xml.aspx'
ORDERS_CHAR_URL = '/char/MarketOrders.xml.aspx'
ORDERS_CORP_URL = '/corp/MarketOrders.xml.aspx'
SKILL_QUEUE_URL = '/char/SkillQueue.xml.aspx'
STANDINGS_URL = '/char/Standings.xml.aspx'
TRANSACTIONS_CHAR_URL = '/char/WalletTransactions.xml.aspx'
TRANSACTIONS_CORP_URL = '/corp/WalletTransactions.xml.aspx'

# number of rows to request per WalletTransactions call, max is 2560
TRANSACTION_ROWS = 2560

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
                start = time.time()

                try:
                    job.run()
                except:
                    logging.error('Trapped exception!', exc_info=sys.exc_info())
                    transaction.rollback()
                else:
                    if settings.DEBUG:
                        with _debug_lock:
                            debug = open('/tmp/api.debug', 'a')
                            debug.write('\n|| %s ||\n' % (job.__class__.__name__))
                            debug.write('%.3fs  %d queries (%.3fs)  API: %.2fs\n' % (time.time() - start,
                                len(connection.queries), sum(float(q['time']) for q in connection.queries),
                                job.api_total_time
                            ))
                            debug.write('\n')
                            for query in connection.queries:
                                if query['sql'].startswith('INSERT INTO "thing_apicache"'):
                                    debug.write('%02.3fs  INSERT INTO "thing_apicache" ...\n' % (float(query['time']),))
                                else:
                                    debug.write('%02.3fs  %s\n' % (float(query['time']), query['sql']))
                            debug.close()

                            connection.queries = []

                self.queue.task_done()

# ---------------------------------------------------------------------------

class APIJob:
    def __init__(self, apikey, character=None):
        self.apikey = apikey
        self.character = character

        self.root = None
        self.apicache = None

        self.api_total_time = 0.0
    
    # ---------------------------------------------------------------------------
    # Perform an API request and parse the returned XML via ElementTree
    def fetch_api(self, url, params, use_auth=True, log_error=True):
        # Add the API key information
        if use_auth:
            params['keyID'] = self.apikey.keyid
            params['vCode'] = self.apikey.vcode

        # Check the API cache for this URL/params combo
        now = datetime.datetime.utcnow()
        params_repr = repr(sorted(params.items()))
        
        try:
            apicache = APICache.objects.get(url=url, parameters=params_repr, cached_until__gt=now)

        # Data is not cached, fetch new data
        except APICache.DoesNotExist:
            apicache = None
            
            full_url = urljoin(settings.API_HOST, url)
            logging.info('Fetching URL %s', full_url)

            # Fetch the URL
            start = time.time()
            
            r = requests.post(full_url, params, headers=HEADERS, config={ 'max_retries': 1 })
            data = r.text
            
            duration = time.time() - start
            self.api_total_time += duration
            logging.info('URL retrieved in %.2fs', duration)

            # If the status code is bad return False
            if not r.status_code == requests.codes.ok:
                return False

        # Data is cached, use that
        else:
            logging.info('Cached URL %s', url)
            data = apicache.text

        # Parse the data if there is any
        if data:
            self.root = ET.fromstring(data.encode('utf-8'))
            current = parse_api_date(self.root.find('currentTime').text)
            until = parse_api_date(self.root.find('cachedUntil').text)

            # If the data wasn't cached, cache it now
            if apicache is None:
                apicache = APICache(
                    url=url,
                    parameters=params_repr,
                    text=data,
                    cached_until=until,
                )
                apicache.save()

            # Check for an error node in the XML
            error = self.root.find('error')
            if error is not None:
                if apicache.error_displayed:
                    return False

                if log_error:
                    logging.error('(%s) %s: %s | %s -> %s', self.__class__.__name__, error.attrib['code'], error.text, current, until)

                # Mark key as invalid if it's an auth error
                if error.attrib['code'] in ('202', '203', '204', '205', '210', '212', '207', '220', '222', '223'):
                    self.apikey.valid = False
                    self.apikey.save()
                
                apicache.error_displayed = True
                apicache.save()
                
                return False

        self.apicache = apicache

        #return (root, times, apicache)
        return True

# ---------------------------------------------------------------------------
# Do various API key things
class APICheck(APIJob):
    def run(self):
        if self.fetch_api(API_INFO_URL, {}) is False or self.root is None:
            return

        # Check for errors
        #err = root.find('error')
        #if err is not None:
            # 202/203/204/205/210/212 Authentication failure
            # 207 Not available for NPC corporations
            # 220 Invalid corporate key
            # 222 Key has expired
            # 223 Legacy API key
        #    if err.attrib['code'] in ('202', '203', '204', '205', '210', '212', '207', '220', '222', '223'):
        #        self.apikey.valid = False
        #        self.apikey.save()

        #    return
        
        # Find the key node
        key_node = self.root.find('result/key')
        # Update access mask
        self.apikey.access_mask = int(key_node.attrib['accessMask'])
        # Update expiry date
        expires = key_node.attrib['expires']
        if expires:
            self.apikey.expires = parse_api_date(expires)
        # Update key type
        self.apikey.key_type = key_node.attrib['type']
        
        # Handle character key type keys
        if key_node.attrib['type'] in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
            seen_chars = {}
            
            for row in key_node.findall('rowset/row'):
                characterID = int(row.attrib['characterID'])
                
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
                # Character exists, update API key and corporation information
                else:
                    character = characters[0]
                    character.corporation = corp
                
                # Save the character
                character.save()
                seen_chars[character.id] = character
            
            # Iterate over all APIKeys with this (keyid, vcode) combo
            for ak in APIKey.objects.filter(keyid=self.apikey.keyid, vcode=self.apikey.vcode):
                # Add characters to this APIKey
                ak.characters.add(*seen_chars.values())

                # Remove any unseen characters from the APIKey
                ak.characters.exclude(pk__in=seen_chars.keys()).delete()
        
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
            
            self.apikey.corp_character = character
        
        # Save any APIKey changes
        self.apikey.save()

        # completed ok
        self.apicache.completed()

# ---------------------------------------------------------------------------
# Fetch account status
class AccountStatus(APIJob):
    def run(self):
        # Don't check corporate keys
        if self.apikey.corp_character:
            return

        # Make sure the access mask matches
        if (self.apikey.access_mask & 33554432) == 0:
            return

        # Fetch the API data
        if self.fetch_api(ACCOUNT_INFO_URL, {}) is False or self.root is None:
            return

        # Update paid_until
        self.apikey.paid_until = parse_api_date(self.root.findtext('result/paidUntil'))

        self.apikey.save()
        
        # completed ok
        self.apicache.completed()

# ---------------------------------------------------------------------------
# Fetch assets
class Assets(APIJob):
    def run(self):
        # Initialise for corporate query
        if self.apikey.corp_character:
            mask = 2
            url = ASSETS_CORP_URL
            a_filter = Asset.objects.filter(corporation=self.apikey.corp_character.corporation)
        # Initialise for character query
        else:
            mask = 2
            url = ASSETS_CHAR_URL
            a_filter = Asset.objects.filter(character=self.character, corporation__isnull=True)

        # Make sure the access mask matches
        if (self.apikey.access_mask & mask) == 0:
            return

        # Fetch the API data
        params = { 'characterID': self.character.id }
        if self.fetch_api(url, params) is False or self.root is None:
            return

        # Generate an asset_id map
        asset_ids = set()
        asset_map = {}
        for asset in a_filter:
            asset_map[asset.id] = asset

        # ACTIVATE RECURSION :siren:
        rows = OrderedDict()
        self.assets_recurse(rows, self.root.find('result/rowset'), None)

        # assetID - [0]system, [1]station, [2]container_id, [3]item, [4]flag, [5]quantiy, [6]rawQuantity, [7]singleton
        errors = 0
        last_count = 9999999999999999
        while rows:
            assets = list(rows.items())
            # check for infinite loops
            count = len(assets)
            if count == last_count:
                logging.warn('Infinite loop in assets, oops')
                return
            last_count = count
            
            # data = [system, station, container_id, item, flag, quantity, rawQuantity, singleton]
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
                        character=self.character,
                        system=data[0],
                        station=data[1],
                        parent=parent,
                        item=data[3],
                        inv_flag_id=data[4],
                        quantity=data[5],
                        raw_quantity=data[6],
                        singleton=data[7],
                    )
                    if self.apikey.corp_character:
                        asset.corporation = self.apikey.corp_character.corporation
                    asset.save()

                    asset_map[id] = asset

                asset_ids.add(id)
                del rows[id]

        # Delete any assets that we didn't see now
        a_filter.exclude(pk__in=asset_ids).delete()

        # completed ok
        self.apicache.completed()

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
        if (self.apikey.access_mask & 8) == 0:
            return
        
        # Fetch the API data
        params = { 'characterID': self.character.id }
        if self.fetch_api(CHAR_SHEET_URL, params) is False or self.root is None:
            return
        
        # Update wallet balance
        self.character.wallet_balance = self.root.findtext('result/balance')
        
        # Update attributes
        self.character.cha_attribute = self.root.findtext('result/attributes/charisma')
        self.character.int_attribute = self.root.findtext('result/attributes/intelligence')
        self.character.mem_attribute = self.root.findtext('result/attributes/memory')
        self.character.per_attribute = self.root.findtext('result/attributes/perception')
        self.character.wil_attribute = self.root.findtext('result/attributes/willpower')
        
        # Update attribute bonuses :ccp:
        enh = self.root.find('result/attributeEnhancers')

        val = enh.find('charismaBonus/augmentatorValue')
        if val is None:
            self.character.cha_bonus = 0
        else:
            self.character.cha_bonus = val.text

        val = enh.find('intelligenceBonus/augmentatorValue')
        if val is None:
            self.character.int_bonus = 0
        else:
            self.character.int_bonus = val.text

        val = enh.find('memoryBonus/augmentatorValue')
        if val is None:
            self.character.mem_bonus = 0
        else:
            self.character.mem_bonus = val.text

        val = enh.find('perceptionBonus/augmentatorValue')
        if val is None:
            self.character.per_bonus = 0
        else:
            self.character.per_bonus = val.text

        val = enh.find('willpowerBonus/augmentatorValue')
        if val is None:
            self.character.wil_bonus = 0
        else:
            self.character.wil_bonus = val.text

        # Update clone information
        self.character.clone_skill_points = self.root.findtext('result/cloneSkillPoints')
        self.character.clone_name = self.root.findtext('result/cloneName')

        # Get all of the rowsets
        rowsets = self.root.findall('result/rowset')
        
        # First rowset is skills
        skills = {}
        for row in rowsets[0]:
            skills[int(row.attrib['typeID'])] = (int(row.attrib['skillpoints']), int(row.attrib['level']))
        
        # Grab any already existing skills
        for char_skill in CharacterSkill.objects.select_related('item', 'skill').filter(character=self.character, skill__in=skills.keys()):
            points, level = skills[char_skill.skill.item_id]
            if char_skill.points != points or char_skill.level != level:
                char_skill.points = points
                char_skill.level = level
                char_skill.save()
            
            del skills[char_skill.skill.item_id]
        
        # Add any leftovers
        for skill_id, (points, level) in skills.items():
            char_skill = CharacterSkill(
                character=self.character,
                skill_id=skill_id,
                points=points,
                level=level,
            )
            char_skill.save()
        
        # Save character
        self.character.save()
        
        # completed ok
        self.apicache.completed()

# ---------------------------------------------------------------------------
# Fetch and add/update character skill queue
class CharacterSkillQueue(APIJob):
    def run(self):
        # Make sure the access mask matches
        if (self.apikey.access_mask & 262144) == 0:
            return
        
        # Fetch the API data
        params = { 'characterID': self.character.id }
        if self.fetch_api(SKILL_QUEUE_URL, params) is False or self.root is None:
            return
        
        # Delete the old queue
        SkillQueue.objects.filter(character=self.character).delete()
        
        # Add new skills
        for row in self.root.findall('result/rowset/row'):
            if row.attrib['startTime'] and row.attrib['endTime']:
                sq = SkillQueue(
                    character=self.character,
                    skill_id=row.attrib['typeID'],
                    start_time=row.attrib['startTime'],
                    end_time=row.attrib['endTime'],
                    start_sp=row.attrib['startSP'],
                    end_sp=row.attrib['endSP'],
                    to_level=row.attrib['level'],
                )
                sq.save()
        
        # completed ok
        self.apicache.completed()

# ---------------------------------------------------------------------------
# Fetch contracts
_contracts_lock = threading.Lock()
class Contracts(APIJob):
    def run(self):
        now = datetime.datetime.now()

        # Generate a character id map
        self.char_id_map = {}
        for character in Character.objects.all():
            self.char_id_map[character.id] = character


        # Initialise for corporate query
        if self.apikey.corp_character:
            mask = 8388608
            url = CONTRACTS_CORP_URL
            params = {}
            c_filter = Contract.objects.filter(
                Q(issuer_corp_id=self.character.corporation.id) |
                Q(assignee_corp_id=self.character.corporation.id) |
                Q(acceptor_corp_id=self.character.corporation.id),
                for_corp=True,
            )
        
        # Initialise for character query
        else:
            mask = 67108864
            url = CONTRACTS_CHAR_URL
            params = { 'characterID': self.character.id }
            c_filter = Contract.objects.filter(
                Q(issuer_char_id=self.character.id) |
                Q(assignee_char_id=self.character.id) |
                Q(acceptor_char_id=self.character.id),
                for_corp=False,
            )
        
        # Make sure the access mask matches
        if (self.apikey.access_mask & mask) == 0:
            return


        if self.fetch_api(url, params) is False or self.root is None:
            return


        # First we need to get all of the acceptor and assignee IDs
        contract_ids = set()
        station_ids = set()
        lookup_ids = set()
        contract_rows = []
        # <row contractID="58108507" issuerID="2004011913" issuerCorpID="751993277" assigneeID="401273477"
        #      acceptorID="0" startStationID="60014917" endStationID="60003760" type="Courier" status="Outstanding"
        #      title="" forCorp="0" availability="Private" dateIssued="2012-08-02 06:50:29" dateExpired="2012-08-09 06:50:29"
        #      dateAccepted="" numDays="7" dateCompleted="" price="0.00" reward="3000000.00" collateral="0.00" buyout="0.00"
        #      volume="10000"/>
        for row in self.root.findall('result/rowset/row'):
            # corp keys don't care about non-corp orders
            if self.apikey.corp_character and row.attrib['forCorp'] == '0':
                continue
            # non-corp keys don't care about corp orders
            if not self.apikey.corp_character and row.attrib['forCorp'] == '1':
                continue

            contract_ids.add(int(row.attrib['contractID']))
            
            station_ids.add(int(row.attrib['startStationID']))
            station_ids.add(int(row.attrib['endStationID']))

            lookup_ids.add(int(row.attrib['issuerID']))
            lookup_ids.add(int(row.attrib['issuerCorpID']))

            if row.attrib['assigneeID'] != '0':
                lookup_ids.add(int(row.attrib['assigneeID']))
            if row.attrib['acceptorID'] != '0':
                lookup_ids.add(int(row.attrib['acceptorID']))
            contract_rows.append(row)

        # Fetch existing chars and corps
        char_map = SimpleCharacter.objects.in_bulk(lookup_ids)
        corp_map = Corporation.objects.in_bulk(lookup_ids)
        new_ids = list(lookup_ids.difference(char_map, corp_map))

        new_chars = []
        new_corps = []

        # Go look up all of those names now
        lookup_map = {}
        for i in range(0, len(new_ids), 250):
            params = { 'ids': ','.join(map(str, new_ids[i:i+250])) }
            if self.fetch_api(CHAR_NAME_URL, params, use_auth=False) is False or self.root is None:
                return

            # <row name="Tazuki Falorn" characterID="1759080617"/>
            for row in self.root.findall('result/rowset/row'):
                id = int(row.attrib['characterID'])
                name = row.attrib['name']

                # Must be a corporation if it has 3 or more spaces
                if name.count(' ') >= 3:
                    new_corps.append(Corporation(
                        id=id,
                        name=name,
                    ))
                else:
                    lookup_map[id] = name

        # Ugh, now go look up all of the damn names just in case they're corporations
        for id, name in lookup_map.items():
            # Serialise access so the APIcache doesn't get completely broken. Also so
            # we don't make CCP mad.
            with _contracts_lock:
                params = { 'corporationID': id }
                # Not a corporation
                if self.fetch_api(CORP_SHEET_URL, params, use_auth=False, log_error=False) is False or self.root is None:
                    new_chars.append(SimpleCharacter(
                        id=id,
                        name=name,
                    ))
                else:
                    new_corps.append(Corporation(
                        id=id,
                        name=name,
                        ticker=self.root.find('result/ticker').text,
                    ))

        # Now we can go create all of those new objects
        with _contracts_lock:
            char_map = SimpleCharacter.objects.in_bulk([c.id for c in new_chars])
            new_chars = [c for c in new_chars if c.id not in char_map]
            SimpleCharacter.objects.bulk_create(new_chars)

            corp_map = Corporation.objects.in_bulk([c.id for c in new_corps])
            new_corps = [c for c in new_corps if c.id not in corp_map]
            Corporation.objects.bulk_create(new_corps)


            # And fetch existing data yet again
            char_map = SimpleCharacter.objects.in_bulk(lookup_ids)
            corp_map = Corporation.objects.in_bulk(lookup_ids)
            station_map = Station.objects.in_bulk(station_ids)

            # Fetch all existing contracts
            c_map = {}
            for contract in c_filter.filter(contract_id__in=contract_ids):
                c_map[contract.contract_id] = contract


            # Finally, after all of that other bullshit, we can actually deal with
            # our goddamn contract rows
            new_contracts = []
            new_events = []

            # <row contractID="58108507" issuerID="2004011913" issuerCorpID="751993277" assigneeID="401273477"
            #      acceptorID="0" startStationID="60014917" endStationID="60003760" type="Courier" status="Outstanding"
            #      title="" forCorp="0" availability="Private" dateIssued="2012-08-02 06:50:29" dateExpired="2012-08-09 06:50:29"
            #      dateAccepted="" numDays="7" dateCompleted="" price="0.00" reward="3000000.00" collateral="0.00" buyout="0.00"
            #      volume="10000"/>
            for row in contract_rows:
                contractID = int(row.attrib['contractID'])
                
                assigneeID = int(row.attrib['assigneeID'])
                if assigneeID == 0:
                    assignee_char = None
                    assignee_corp = None
                elif assigneeID in char_map:
                    assignee_char = char_map[assigneeID]
                    assignee_corp = None
                else:
                    assignee_char = None
                    assignee_corp = corp_map[assigneeID]

                acceptorID = int(row.attrib['acceptorID'])
                if acceptorID == 0:
                    acceptor_char = None
                    acceptor_corp = None
                elif acceptorID in char_map:
                    acceptor_char = char_map[acceptorID]
                    acceptor_corp = None
                else:
                    acceptor_char = None
                    acceptor_corp = corp_map[acceptorID]

                dateIssued = parse_api_date(row.attrib['dateIssued'])
                dateExpired = parse_api_date(row.attrib['dateIssued'])
                
                dateAccepted = row.attrib['dateIssued']
                if dateAccepted:
                    dateAccepted = parse_api_date(dateAccepted)
                else:
                    dateAccepted = None

                dateCompleted = row.attrib['dateIssued']
                if dateCompleted:
                    dateCompleted = parse_api_date(dateCompleted)
                else:
                    dateCompleted = None

                type = row.attrib['type']
                if type == 'ItemExchange':
                    type = 'Item Exchange'

                contract = c_map.get(contractID, None)
                # Contract exists, maybe update stuff
                if contract is not None:
                    if contract.status != row.attrib['status']:
                        text = 'Contract #%d (%s, %s) changed status from %s to %s' % (
                            contract.contract_id, contract.type, contract.start_station.short_name,
                            contract.status, row.attrib['status'])
                        
                        new_events.append(Event(
                            user_id=self.apikey.user.id,
                            issued=now,
                            text=text,
                        ))

                        contract.status = row.attrib['status']
                        contract.dateAccepted = dateAccepted
                        contract.dateCompleted = dateCompleted
                        contract.save()

                # Contract does not exist, make a new one
                else:
                    new_contracts.append(Contract(
                        contract_id=contractID,
                        issuer_char=char_map[int(row.attrib['issuerID'])],
                        issuer_corp=corp_map[int(row.attrib['issuerCorpID'])],
                        assignee_char=assignee_char,
                        assignee_corp=assignee_corp,
                        acceptor_char=acceptor_char,
                        acceptor_corp=acceptor_corp,
                        start_station=station_map[int(row.attrib['startStationID'])],
                        end_station=station_map[int(row.attrib['endStationID'])],
                        type=type,
                        status=row.attrib['status'],
                        title=row.attrib['title'],
                        for_corp=(row.attrib['forCorp'] == '1'),
                        public=(row.attrib['availability'].lower() == 'public'),
                        date_issued=dateIssued,
                        date_expired=dateExpired,
                        date_accepted=dateAccepted,
                        date_completed=dateCompleted,
                        num_days=int(row.attrib['numDays']),
                        price=Decimal(row.attrib['price']),
                        reward=Decimal(row.attrib['reward']),
                        collateral=Decimal(row.attrib['collateral']),
                        buyout=Decimal(row.attrib['buyout']),
                        volume=Decimal(row.attrib['volume']),
                    ))
            
            # And save the damn things
            Contract.objects.bulk_create(new_contracts)
            Event.objects.bulk_create(new_events)

        
        # completed ok
        #self.apicache.completed()

# ---------------------------------------------------------------------------
# Fetch corporation sheet
class CorporationSheet(APIJob):
    def run(self):
        # Make sure the access mask matches
        if (self.apikey.access_mask & 8) == 0:
            return
        
        params = { 'characterID': self.apikey.corp_character_id }
        if self.fetch_api(CORP_SHEET_URL, params) is False or self.root is None:
            return
        
        corporation = self.apikey.corp_character.corporation
        
        ticker = self.root.find('result/ticker')
        corporation.ticker = ticker.text
        corporation.save()
        
        errors = 0
        for rowset in self.root.findall('result/rowset'):
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
            self.apicache.completed()

# ---------------------------------------------------------------------------
# Fetch corporation wallets
class CorporationWallets(APIJob):
    def run(self):
        # Make sure the access mask matches
        if (self.apikey.access_mask & 1) == 0:
            return
        
        params = { 'characterID': self.apikey.corp_character_id }
        if self.fetch_api(BALANCE_URL, params) is False or self.root is None:
            return
        
        corporation = self.apikey.corp_character.corporation
        wallet_map = {}
        for cw in CorpWallet.objects.filter(corporation=corporation):
            wallet_map[cw.account_key] = cw
        
        for row in self.root.findall('result/rowset/row'):
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
        self.apicache.completed()

# ---------------------------------------------------------------------------
# Fetch locations (and more importantly names) for assets
class Locations(APIJob):
    def run(self):
        # Initialise for character query
        if not self.apikey.corp_character:
            mask = 134217728
            url = LOCATIONS_CHAR_URL
            a_filter = Asset.objects.root_nodes().filter(character=self.character, corporation__isnull=True, singleton=True, item__item_group__category__name__in=('Celestial', 'Ship'))

        # Make sure the access mask matches
        if (self.apikey.access_mask & mask) == 0:
            return

        # Get ID list
        ids = map(str, a_filter.values_list('id', flat=True))
        if len(ids) == 0:
            return

        # Fetch the API data
        params = {
            'characterID': self.character.id,
            'IDs': ','.join(map(str, ids)),
        }
        if self.fetch_api(url, params) is False or self.root is None:
            return

        for row in self.root.findall('result/rowset/row'):
            ca = Asset.objects.get(character=self.character, id=row.attrib['itemID'])
            if ca.name is None or ca.name != row.attrib['itemName']:
                ca.name = row.attrib['itemName']
                ca.save()
        
        # completed ok
        self.apicache.completed()

# ---------------------------------------------------------------------------
# Fetch and add/update market orders
class MarketOrders(APIJob):
    def run(self):
        # Generate a character id map
        self.char_id_map = {}
        for character in Character.objects.all():
            self.char_id_map[character.id] = character


        # Initialise for corporate query
        if self.apikey.corp_character:
            mask = 4096
            url = ORDERS_CORP_URL
            o_filter = MarketOrder.objects.filter(corp_wallet__corporation=self.character.corporation)
            
            wallet_map = {}
            for cw in CorpWallet.objects.filter(corporation=self.character.corporation):
                wallet_map[cw.account_key] = cw
        
        # Initialise for character query
        else:
            mask = 4096
            url = ORDERS_CHAR_URL
            o_filter = MarketOrder.objects.filter(corp_wallet=None, character=self.character)
        
        # Make sure the access mask matches
        if (self.apikey.access_mask & mask) == 0:
            return
        
        # Fetch the API data
        params = { 'characterID': self.character.id }
        if self.fetch_api(url, params) is False or self.root is None:
            return
        
        # Generate an order_id map
        order_map = {}
        for mo in o_filter.select_related('item'):
            order_map[mo.order_id] = mo
        
        # Iterate over the returned result set
        seen = []
        for row in self.root.findall('result/rowset/row'):
            order_id = int(row.attrib['orderID'])
            
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
                        order.issued = issued
                        order.expires = issued + datetime.timedelta(int(row.attrib['duration']))
                        order.volume_remaining = volRemaining
                        order.escrow = escrow
                        order.price = price
                        order.total_price = order.volume_remaining * order.price
                        order.save()
                    
                    seen.append(order_id)
                
                # Not active, delete order
                #else:
                #    order.delete()
            
            # Doesn't exist and is active, make a new order
            elif row.attrib['orderState'] == '0':
                buy_order = (row.attrib['bid'] == '1')
                #if row.attrib['bid'] == '0':
                #    buy_order = False
                #else:
                #    buy_order = True
                
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
                if self.apikey.corp_character:
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
                user_id=self.apikey.user.id,
                issued=now,
                text=text,
            )
            event.save()

        # Then delete
        to_delete.delete()
        
        # completed ok
        self.apicache.completed()

# ---------------------------------------------------------------------------
# Fetch character standings
class Standings(APIJob):
    def run(self):
        if self.apikey.corp_character:
            logging.warn('Corporate APIKey passed to Standings!')
            return

        # Make sure the access mask matches
        if (self.apikey.access_mask & 524288) == 0:
            return
        
        # Fetch the API data
        params = { 'characterID': self.character.id }
        if self.fetch_api(STANDINGS_URL, params) is False or self.root is None:
            return
        
        # Build data maps
        corp_map = {}
        for cs in CorporationStanding.objects.filter(character=self.character):
            corp_map[cs.corporation_id] = cs

        faction_map = {}
        for fs in FactionStanding.objects.filter(character=self.character):
            faction_map[fs.faction_id] = fs

        # Iterate over rowsets
        for rowset in self.root.findall('result/characterNPCStandings/rowset'):
            name = rowset.attrib['name']

            # NYI: Agents
            if name == 'agents':
                continue

            # Corporations
            elif name == 'NPCCorporations':
                new = []
                for row in rowset.findall('row'):
                    id = int(row.attrib['fromID'])
                    standing = Decimal(row.attrib['standing'])

                    cs = corp_map.get(id, None)
                    # Standing doesn't exist, make a new one
                    if cs is None:
                        cs = CorporationStanding(
                            character_id=self.character.id,
                            corporation_id=id,
                            standing=standing,
                        )
                        new.append(cs)
                    # Exists, check for standings change
                    else:
                        if cs.standing != standing:
                            cs.standing = standing
                            cs.save()

                if new:
                    CorporationStanding.objects.bulk_create(new)

            # Factions
            elif name == 'factions':
                new = []
                for row in rowset.findall('row'):
                    id = int(row.attrib['fromID'])
                    standing = Decimal(row.attrib['standing'])

                    fs = faction_map.get(id, None)
                    # Standing doesn't exist, make a new one
                    if fs is None:
                        fs = FactionStanding(
                            character_id=self.character.id,
                            faction_id=id,
                            standing=standing,
                        )
                        new.append(fs)
                    # Exists, check for standings change
                    else:
                        if fs.standing != standing:
                            fs.standing = standing
                            fs.save()

                if new:
                    FactionStanding.objects.bulk_create(new)

        # completed ok
        self.apicache.completed()

# ---------------------------------------------------------------------------
# Fetch wallet transactions
class WalletTransactions(APIJob):
    def run(self):
        start = time.time()

        # Generate a character id map
        self.char_id_map = {}
        for character in Character.objects.all():
            self.char_id_map[character.id] = character

        # Initialise stuff
        params = {
            'characterID': self.character.id,
            'rowCount': TRANSACTION_ROWS,
        }
        
        # Corporate key
        if self.apikey.corp_character:
            params['accountKey'] = self._corp_wallet.account_key
            mask = 2097152
            url = TRANSACTIONS_CORP_URL
            t_filter = Transaction.objects.filter(corp_wallet=self._corp_wallet)
        # Character key
        else:
            mask = 4194304
            url = TRANSACTIONS_CHAR_URL
            t_filter = Transaction.objects.filter(corp_wallet=None, character=self.character)
        
        # Make sure the access mask matches
        if (self.apikey.access_mask & mask) == 0:
            return

        # Loop until we run out of transactions
        cursor = connection.cursor()

        while True:
            if self.fetch_api(url, params) is False or self.root is None:
                break
            
            start = time.time()

            errors = 0
            
            rows = self.root.findall('result/rowset/row')
            # empty result set = no transactions ever on this wallet
            if not rows:
                self.apicache.completed()
                break
            
            # Make a transaction id:row map
            bulk_data = OrderedDict()
            client_ids = set()
            for row in rows:
                transaction_id = int(row.attrib['transactionID'])
                bulk_data[transaction_id] = row
                client_ids.add(int(row.attrib['clientID']))

            t1 = time.time()
            logging.info('WalletTransactions bulk_data took %.3fs', t1 - start)

            t_map = {}
            for t in t_filter.filter(transaction_id__in=bulk_data.keys()).values('id', 'transaction_id', 'other_char_id', 'other_corp_id'):
                t_map[t['transaction_id']] = t

            t2 = time.time()
            logging.info('WalletTransactions t_map took %.3fs', t2 - t1)

            # Fetch simplechars and corporations for clients
            simple_map = SimpleCharacter.objects.in_bulk(client_ids)
            corp_map = Corporation.objects.in_bulk(client_ids)

            t3 = time.time()
            logging.info('WalletTransactions client maps took %.3fs', t3 - t2)
            
            # Now iterate over the leftovers
            new = []
            for transaction_id, row in bulk_data.items():
                # Initalise some variables
                transaction_time = parse_api_date(row.attrib['transactionDateTime'])
                
                # Skip corporate transactions if this is a personal call, we have no idea
                # what wallet this transaction is related to otherwise :ccp:
                if row.attrib['transactionFor'].lower() == 'corporation' and not self.apikey.corp_character:
                    continue
                
                client_id = int(row.attrib['clientID'])
                client = simple_map.get(client_id, corp_map.get(client_id, None))
                if client is None:
                    try:
                        client = SimpleCharacter.objects.create(
                            id=client_id,
                            name=row.attrib['clientName']
                        )
                    except IntegrityError:
                        client = SimpleCharacter.objects.get(id=client_id)

                    simple_map[client_id] = client

                # Check to see if this transaction already exists
                t = t_map.get(transaction_id, None)
                if t is None:
                    # Make sure the item typeID is valid
                    #items = Item.objects.filter(pk=row.attrib['typeID'])
                    #if items.count() == 0:
                    #    print "ERROR: item with typeID '%s' does not exist, what the fuck?" % (row.attrib['typeID'])
                    #    print '>> attrib = %r' % (row.attrib)
                    #    continue
                    
                    # Make the station object if it doesn't already exist
                    station = get_station(int(row.attrib['stationID']))
                    
                    # For a corporation key, make sure the character exists
                    if self.apikey.corp_character:
                        char_id = int(row.attrib['characterID'])
                        char = self.char_id_map.get(char_id, None)
                        # Doesn't exist, create it
                        if char is None:
                            char = Character(
                                id=char_id,
                                name=row.attrib['characterName'],
                                corporation=self.apikey.corp_character.corporation,
                            )
                            char.save()
                            self.char_id_map[char_id] = char
                    # Any other key = just use the supplied character
                    else:
                        char = self.character
                    
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
                        item=get_item(row.attrib['typeID']),
                        character=char,
                        transaction_id=transaction_id,
                        date=transaction_time,
                        buy_transaction=buy_transaction,
                        quantity=quantity,
                        price=price,
                        total_price=quantity * price,
                    )
                    # Set the corp_character for corporation API requests
                    if self.apikey.corp_character:
                        t.corp_wallet = self._corp_wallet
                    # Set whichever client type is relevant
                    if isinstance(client, SimpleCharacter):
                        t.other_char_id = client.id
                    else:
                        t.other_corp_id = client.id
                    #t.save()
                    new.append(t)

                # Transaction exists, check the other_ fields
                else:
                    if t['other_char_id'] is None and t['other_corp_id'] is None:
                        if isinstance(client, SimpleCharacter):
                            cursor.execute('UPDATE thing_transaction SET other_char_id = %s WHERE id = %s', (client.id, t['id']))
                        else:
                            cursor.execute('UPDATE thing_transaction SET other_corp_id = %s WHERE id = %s', (client.id, t['id']))
                        logging.info('Updated other_ field of transaction %s', t['id'])

            t4 = time.time()
            logging.info('WalletTransactions loop took %.3fs', t4 - t3)
            
            # Create any new transaction objects
            t5 = time.time()
            Transaction.objects.bulk_create(new)
            logging.info('WalletTransactions insert took %.2fs', time.time() - t5)

            # completed ok
            if errors == 0:
                self.apicache.completed()

            # If we got MAX rows we should retrieve some more
            if len(bulk_data) == TRANSACTION_ROWS:
                params['beforeTransID'] = transaction_id
            else:
                break
        
        logging.info('WalletTransactions took %.2fs', time.time() - start)
        

# ---------------------------------------------------------------------------
# Cleanup any out-of-date cached API requests
class CleanupCache(APIJob):
    def run(self):
        now = datetime.datetime.utcnow()
        APICache.objects.filter(cached_until__lt=now).delete()

# ---------------------------------------------------------------------------

_debug_lock = threading.Lock()
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
        for i in range(settings.API_THREADS):
            t = APIWorker(self._job_queue)
            t.start()
            self._threads.append(t)

        # zero out api.debug
        if settings.DEBUG:
            open('/tmp/api.debug', 'w')

    def stop_threads(self):
        for t in self._threads:
            self._job_queue.put(None)

        self._job_queue.join()

    def go(self):
        start = time.time()

        # Make sure API keys are valid first
        seen_keys = set()
        any_valid = False
        for apikey in APIKey.objects.select_related().filter(valid=True).order_by('key_type'):
            # Don't visit keyid/vcode combos that we've already visited
            if (apikey.keyid, apikey.vcode) in seen_keys:
                continue
            seen_keys.add((apikey.keyid, apikey.vcode))

            job = APICheck(apikey)
            self._job_queue.put(job)
            any_valid = True

        # Wait for all key checks to be completed
        if not any_valid:
            logging.info('No valid APIKeys, exiting')
            return

        self._job_queue.join()

        # Now we can get down to business
        seen_keys = set()
        
        apikeys = APIKey.objects.select_related('corp_character__corporation')
        apikeys = apikeys.prefetch_related('characters', 'corp_character__corporation__corpwallet_set')
        apikeys = apikeys.filter(valid=True, access_mask__isnull=False)

        for apikey in apikeys:
            # Don't visit keyid/vcode combos that we've already visited
            if (apikey.keyid, apikey.vcode) in seen_keys:
                continue
            seen_keys.add((apikey.keyid, apikey.vcode))

            # Make sure account status is up to date
            job = AccountStatus(apikey)
            self._job_queue.put(job)

            # Account/Character key are basically the same thing
            if apikey.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
                for character in apikey.characters.all():
                    # Fetch character sheet
                    job = CharacterSheet(apikey, character)
                    self._job_queue.put(job)

                    # Fetch character skill queue
                    job = CharacterSkillQueue(apikey, character)
                    self._job_queue.put(job)
                    
                    # Fetch market orders
                    job = MarketOrders(apikey, character)
                    self._job_queue.put(job)
                    
                    # Fetch standings
                    job = Standings(apikey, character)
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

                    # Fetch contracts
                    job = Contracts(apikey, character)
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
                for corp_wallet in corporation.corpwallet_set.all():#CorpWallet.objects.filter(corporation=corporation):
                    job = WalletTransactions(apikey, character)
                    job._corp_wallet = corp_wallet
                    self._job_queue.put(job)

                # Fetch assets
                job = Assets(apikey, character)
                self._job_queue.put(job)

                # Fetch contracts
                job = Contracts(apikey, character)
                self._job_queue.put(job)

        # Cleanup cache
        job = CleanupCache(None)
        self._job_queue.put(job)

        # All done, wait for jobs to complete then shut down the threads
        self.stop_threads()

        if settings.DEBUG:
            with _debug_lock:
                debug = open('/tmp/api.debug', 'a')
                debug.write('\n|| APIUpdater ||\n')
                debug.write('%.3fs  %d queries (%.3fs)\n' % (time.time() - start,
                    len(connection.queries), sum(float(q['time']) for q in connection.queries)
                ))
                debug.write('\n')
                for query in connection.queries:
                   debug.write('%02.3fs  %s\n' % (float(query['time']), query['sql']))
                debug.close()

# ---------------------------------------------------------------------------
# Turn an API date into a datetime object
#_pad_lock = threading.Lock()
def parse_api_date(s):
    #with _pad_lock:
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
    corp = _corp_cache.get(corp_id, None)
    if corp is None:
        try:
            corp = Corporation.objects.get(pk=corp_id)
        # Corporation doesn't exist, make a new object and save it
        except Corporation.DoesNotExist:
            corp = Corporation(id=corp_id, name=corp_name)
            corp.save()
        
        _corp_cache[corp_id] = corp
    
    return corp

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
