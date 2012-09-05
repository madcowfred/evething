import datetime
import requests
import socket
import sys
import time

from collections import OrderedDict
from decimal import *
from urlparse import urljoin

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import connection, transaction, IntegrityError

from thing import queries
from thing.models import *

from celery import task
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

# ---------------------------------------------------------------------------
# Requests session
_session = requests.session(
    config={
        'pool_maxsize': 1,
        'max_retries': 1
    },
    headers={
        'User-Agent': 'EVEthing-tasks (keep-alive test)',
    },
)

# ---------------------------------------------------------------------------
# random HTTP headers
HEADERS = {
    'User-Agent': 'EVEthing-tasks',
}
# number of rows to request per WalletTransactions call, max is 2560
TRANSACTION_ROWS = 2560

CHAR_NAME_URL = '/eve/CharacterName.xml.aspx'
CORP_SHEET_URL = '/corp/CorporationSheet.xml.aspx'


API_KEY_INFO_URL = ('api_key_info', '/account/APIKeyInfo.xml.aspx', 'et_low')

CHAR_URLS = {
    APIKey.CHAR_ACCOUNT_STATUS_MASK: ('account_status', '/account/AccountStatus.xml.aspx', 'et_medium'),
    APIKey.CHAR_ASSET_LIST_MASK: ('asset_list', '/char/AssetList.xml.aspx', 'et_medium'),
    APIKey.CHAR_CHARACTER_SHEET_MASK: ('character_sheet', '/char/CharacterSheet.xml.aspx', 'et_medium'),
    APIKey.CHAR_CONTRACTS_MASK: ('contracts', '/char/Contracts.xml.aspx', 'et_medium'),
    #APIKey.CHAR_LOCATIONS_MASK: ('locations', '/char/Locations.xml.aspx', 'et_medium'),
    APIKey.CHAR_MARKET_ORDERS_MASK: ('market_orders', '/char/MarketOrders.xml.aspx', 'et_medium'),
    APIKey.CHAR_SKILL_QUEUE_MASK: ('skill_queue', '/char/SkillQueue.xml.aspx', 'et_medium'),
    APIKey.CHAR_STANDINGS_MASK: ('standings', '/char/Standings.xml.aspx', 'et_medium'),
    APIKey.CHAR_WALLET_TRANSACTIONS_MASK: ('wallet_transactions', '/char/WalletTransactions.xml.aspx', 'et_medium'),
}
CORP_URLS = {
    APIKey.CORP_ACCOUNT_BALANCE_MASK: ('account_balance', '/corp/AccountBalance.xml.aspx', 'et_medium'),
    APIKey.CORP_ASSET_LIST_MASK: ('asset_list', '/corp/AssetList.xml.aspx', 'et_medium'),
    APIKey.CORP_CONTRACTS_MASK: ('contracts', '/corp/Contracts.xml.aspx', 'et_medium'),
    APIKey.CORP_CORPORATION_SHEET_MASK: ('corporation_sheet', '/corp/CorporationSheet.xml.aspx', 'et_medium'),
    APIKey.CORP_MARKET_ORDERS_MASK: ('market_orders', '/corp/MarketOrders.xml.aspx', 'et_medium'),
    APIKey.CORP_WALLET_TRANSACTIONS_MASK: ('wallet_transactions', '/corp/WalletTransactions.xml.aspx', 'et_medium'),
}

# ---------------------------------------------------------------------------
# Class to wrap things
class APIJob:
    def __init__(self, apikey_id, taskstate_id):
        self.ready = True

        # Fetch APIKey
        try:
            self.apikey = APIKey.objects.get(pk=apikey_id)
        except APIKey.DoesNotExist:
            self.ready = False
        else:
            # Still valid?
            if not self.apikey.valid:
                self.ready = False

        # Fetch TaskState
        try:
            self.taskstate = TaskState.objects.get(pk=taskstate_id)
        except TaskState.DoesNotExist:
            self.ready = False

        self.root = None
        self.apicache = None

    def completed(self):
        self.apicache.completed()
        self._taskstate_ready()

    def failed(self):
        self._taskstate_ready()

    def _taskstate_ready(self):
        now = datetime.datetime.now()
        self.taskstate.state = TaskState.READY_STATE
        self.taskstate.mod_time = now

        if self.root:
            utc_now = datetime.datetime.utcnow()
            until = parse_api_date(self.root.find('cachedUntil').text)
            diff = until - utc_now
            self.taskstate.next_time = now + diff + datetime.timedelta(seconds=30)
        else:
            # If we have an APICache object, delay until the page is no longer cached
            if self.apicache is not None:
                self.taskstate.next_time = self.apicache.cached_until + datetime.timedelta(seconds=30)
            # No APICache? Just delay for 30 minutes
            else:
                self.taskstate.next_time = now + datetime.timedelta(minutes=30)

        self.taskstate.save()

    # ---------------------------------------------------------------------------
    # Perform an API request and parse the returned XML via ElementTree
    def fetch_api(self, url, params, use_auth=True, log_error=True):
        # Set the task to active
        self.taskstate.state = TaskState.ACTIVE_STATE
        self.taskstate.mod_time = datetime.datetime.now()
        self.taskstate.save()

        # Add the API key information
        if use_auth:
            params['keyID'] = self.apikey.keyid
            params['vCode'] = self.apikey.vcode

        # Check the API cache for this URL/params combo
        now = datetime.datetime.utcnow()
        params_repr = repr(sorted(params.items()))
        
        # Retrieve the latest APICache object
        apicaches = list(APICache.objects.filter(url=url, parameters=params_repr, cached_until__gt=now).order_by('-cached_until')[:1])
        
        # Data is not cached, fetch new data
        if len(apicaches) == 0:
            apicache = None
            
            # Fetch the URL
            full_url = urljoin(settings.API_HOST, url)
            try:
                r = _session.post(full_url, params, prefetch=True)
                data = r.text
            except socket.error:
                return False
            except SoftTimeLimitExceeded:
                return False

            # If the status code is bad return False
            if not r.status_code == requests.codes.ok:
                return False

        # Data is cached, use that
        else:
            apicache = apicaches[0]
            data = apicache.text

        # Parse the data if there is any
        if data:
            try:
                self.root = ET.fromstring(data.encode('utf-8'))
            except ET.ParseError:
                return False

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
                    logger.error('%s: %s | %s -> %s', error.attrib['code'], error.text, current, until)

                # Mark key as invalid if it's an auth error
                if error.attrib['code'] in ('202', '203', '204', '205', '210', '212', '207', '220', '222', '223'):
                    text = "Your API key #%d was marked invalid: %s %s" % (self.apikey.id, error.attrib['code'],
                        error.text)
                    Event.objects.create(
                        user_id=self.apikey.user.id,
                        issued=now,
                        text=text,
                    )

                    self.apikey.valid = False
                    self.apikey.save()
                
                apicache.error_displayed = True
                apicache.save()
                
                return False

        self.apicache = apicache

        return True

# ---------------------------------------------------------------------------
# Periodic task to clean up broken tasks
@task
def taskstate_cleanup():
    now = datetime.datetime.now()
    fifteen_mins_ago = now - datetime.timedelta(minutes=15)
    one_hour_ago = now - datetime.timedelta(minutes=60)

    # Build a QuerySet to find broken tasks
    taskstates = TaskState.objects.filter(
        # Queued for an hour?
        Q(state=TaskState.QUEUED_STATE, mod_time__lt=one_hour_ago)
        |
        # Active for 15 minutes?
        Q(state=TaskState.ACTIVE_STATE, mod_time__lt=fifteen_mins_ago)
    )

    # Set them to restart
    count = taskstates.update(mod_time=now, next_time=now, state=TaskState.READY_STATE)
    if count > 0:
        logger.warn('taskstate_cleanup: reset %d broken tasks', count)

# ---------------------------------------------------------------------------
# Periodic task to clean up expired APICache objects
@task
def apicache_cleanup():
    now = datetime.datetime.utcnow()
    count = APICache.objects.filter(cached_until__lt=now).delete()

# ---------------------------------------------------------------------------
# Periodic task to spawn API jobs
@task
def spawn_jobs():
    # Build a magical QuerySet for APIKey objects
    apikeys = APIKey.objects.select_related('corp_character__corporation')
    apikeys = apikeys.prefetch_related('characters', 'corp_character__corporation__corpwallet_set')
    apikeys = apikeys.filter(valid=True)

    # Get a set of unique API keys
    keys = {}
    status = {}
    for apikey in apikeys:
        key_info = apikey.get_key_info()
        keys[key_info] = apikey
        status[key_info] = {}

    # Check their task states
    for taskstate in TaskState.objects.filter(key_info__in=keys.keys()).iterator():
        status[taskstate.key_info][(taskstate.url, taskstate.parameter)] = taskstate

    # Blah blah
    now = datetime.datetime.now()
    for key_info, apikey in keys.items():
        masks = apikey.get_masks()
        
        # All keys do keyinfo checks things
        func, url, queue = API_KEY_INFO_URL
        taskstate = status[key_info].get((url, 0), None)

        # # If task isn't found, make a new taskstate and queue the task
        # if taskstate is None:
        #     taskstate = TaskState.objects.create(
        #         key_info=key_info,
        #         url=url,
        #         parameter=0,
        #         state=TaskState.QUEUED_STATE,
        #         mod_time=now,
        #         next_time=now,
        #     )

        #     start = True
        
        # # Task was found, find out if it needs starting
        # else:
        #     start = taskstate.queue_now(now)
        #     # Make sure we update the state to queued!
        #     if start:
        #         taskstate.state = TaskState.QUEUED_STATE
        #         taskstate.mod_time = now
        #         taskstate.save()

        # If we need to queue this task, do so
        taskstate, start = _init_taskstate(taskstate, key_info, url, 0, now)
        if start is True:
            f = globals()[func]
            f.apply_async(
                args=(url, apikey.id, taskstate.id),
                queue=queue,
            )


        # Account/character keys
        if apikey.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
            for mask in masks:
                # get useful URL data for this mask
                url_data = CHAR_URLS.get(mask, None)
                if url_data is None:
                    continue

                func, url, queue = url_data

                for character in apikey.characters.all():
                    if mask == APIKey.CHAR_ACCOUNT_STATUS_MASK:
                        parameter = 0
                    else:
                        parameter = character.id

                    taskstate = status[key_info].get((url, parameter), None)

                    # # If task isn't found, make a new taskstate and queue the task
                    # if taskstate is None:
                    #     taskstate = TaskState.objects.create(
                    #         key_info=key_info,
                    #         url=url,
                    #         parameter=parameter,
                    #         state=TaskState.QUEUED_STATE,
                    #         mod_time=now,
                    #         next_time=now,
                    #     )

                    #     start = True

                    # # Task was found, find out if it needs starting
                    # else:
                    #     start = taskstate.queue_now(now)
                    #     # Make sure we update the state to queued!
                    #     if start:
                    #         taskstate.state = TaskState.QUEUED_STATE
                    #         taskstate.mod_time = now
                    #         taskstate.save()

                    # If we need to queue this task, do so
                    taskstate, start = _init_taskstate(taskstate, key_info, url, parameter, now)
                    if start is True:
                        f = globals()[func]
                        f.apply_async(
                            args=(url, apikey.id, taskstate.id, parameter),
                            queue=queue,
                        )

                    # Only do account status once per key
                    if mask == APIKey.CHAR_ACCOUNT_STATUS_MASK:
                        break

        # Corporation keys
        elif apikey.key_type == APIKey.CORPORATION_TYPE:
            character = apikey.corp_character

            for mask in masks:
                # get useful URL data for this mask
                url_data = CORP_URLS.get(mask, None)
                if url_data is None:
                    continue

                func, url, queue = url_data

                taskstate = status[key_info].get((url, character.id), None)

                # # If task isn't found, make a new taskstate and queue the task
                # if taskstate is None:
                #     taskstate = TaskState.objects.create(
                #         key_info=key_info,
                #         url=url,
                #         parameter=character.id,
                #         state=TaskState.QUEUED_STATE,
                #         mod_time=now,
                #         next_time=now,
                #     )

                #     start = True

                # # Task was found, find out if it needs starting
                # else:
                #     start = taskstate.queue_now(now)
                #     # Make sure we update the state to queued!
                #     if start:
                #         taskstate.state = TaskState.QUEUED_STATE
                #         taskstate.mod_time = now
                #         taskstate.save()

                # If we need to queue this task, do so
                taskstate, start = _init_taskstate(taskstate, key_info, url, character.id, now)
                if start is True:
                    f = globals()[func]
                    f.apply_async(
                        args=(url, apikey.id, taskstate.id, character.id),
                        queue=queue,
                    )

def _init_taskstate(taskstate, key_info, url, parameter, now):
    # If task isn't found, make a new taskstate and queue the task
    if taskstate is None:
        taskstate = TaskState.objects.create(
            key_info=key_info,
            url=url,
            parameter=parameter,
            state=TaskState.QUEUED_STATE,
            mod_time=now,
            next_time=now,
        )

        start = True
    
    # Task was found, find out if it needs starting
    else:
        start = taskstate.queue_now(now)
        # Make sure we update the state to queued!
        if start:
            taskstate.state = TaskState.QUEUED_STATE
            taskstate.mod_time = now
            taskstate.save()

    return taskstate, start

# ---------------------------------------------------------------------------
# Account balances
@task
def account_balance(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    #character = Character.objects.get(pk=character_id)

    params = { 'characterID': job.apikey.corp_character_id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return
    
    corporation = job.apikey.corp_character.corporation
    wallet_map = {}
    for cw in corporation.corpwallet_set.all():
        wallet_map[cw.account_key] = cw
    
    new = []
    for row in job.root.findall('result/rowset/row'):
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
            new.append(CorpWallet(
                account_id=accountID,
                corporation=corporation,
                account_key=accountKey,
                description='?',
                balance=balance,
            ))
    
    if new:
        CorpWallet.objects.bulk_create(new)

    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Account status
@task
def account_status(url, apikey_id, taskstate_id, zero):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return

    # Fetch the API data
    if job.fetch_api(url, {}) is False or job.root is None:
        job.failed()
        return

    # Update paid_until
    job.apikey.paid_until = parse_api_date(job.root.findtext('result/paidUntil'))
    job.apikey.save()
    
    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Various API things
@task
def api_key_info(url, apikey_id, taskstate_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return

    # Fetch the API data
    if job.fetch_api(url, {}) is False or job.root is None:
        job.failed()
        return

    # Find the key node
    key_node = job.root.find('result/key')
    
    # Update access mask
    job.apikey.access_mask = int(key_node.attrib['accessMask'])
    
    # Update expiry date
    expires = key_node.attrib['expires']
    if expires:
        job.apikey.expires = parse_api_date(expires)
    else:
        job.apikey.expires = None
    
    # Update key type
    job.apikey.key_type = key_node.attrib['type']
    
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
        for ak in APIKey.objects.filter(keyid=job.apikey.keyid, vcode=job.apikey.vcode):
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
            character.save()
        else:
            character = characters[0]
        
        job.apikey.corp_character = character
    
    # Save any APIKey changes
    job.apikey.save()

    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Fetch assets
@task
def asset_list(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    character = Character.objects.get(pk=character_id)

    # Initialise for corporate query
    if job.apikey.corp_character:
        a_filter = Asset.objects.filter(character=character, corporation_id=job.apikey.corp_character.corporation.id)
    # Initialise for character query
    else:
        a_filter = Asset.objects.filter(character=character, corporation_id__isnull=True)

    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return

    # ACTIVATE RECURSION :siren:
    rows = OrderedDict()
    _asset_list_recurse(rows, job.root.find('result/rowset'), None)

    # Delete existing assets, it's way too much of a bastard to deal with changes
    a_filter.delete()

    # assetID - [0]system, [1]station, [2]container_id, [3]item, [4]flag, [5]quantiy, [6]rawQuantity, [7]singleton
    asset_ids = set()
    asset_map = {}

    errors = 0
    last_count = 9999999999999999
    while rows:
        assets = list(rows.items())
        # check for infinite loops
        count = len(assets)
        if count == last_count:
            logger.warn('Infinite loop in assets, oops')
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

            asset = Asset(
                id=id,
                character=character,
                system=data[0],
                station=data[1],
                parent=parent,
                item=data[3],
                inv_flag_id=data[4],
                quantity=data[5],
                raw_quantity=data[6],
                singleton=data[7],
            )
            if job.apikey.corp_character:
                asset.corporation_id = job.apikey.corp_character.corporation.id
            asset.save()

            asset_map[id] = asset

            asset_ids.add(id)
            del rows[id]

    # completed ok
    job.completed()

# Recursively visit the assets tree and gather data
def _asset_list_recurse(rows, rowset, container_id):
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

        # check for valid item
        item = get_item(row.attrib['typeID'])
        if item is None:
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
            _asset_list_recurse(rows, rowset, asset_id)

# ---------------------------------------------------------------------------
# Update character sheet
@task
def character_sheet(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    character = Character.objects.get(pk=character_id)

    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return
    
    # Update wallet balance
    character.wallet_balance = job.root.findtext('result/balance')
    
    # Update attributes
    character.cha_attribute = job.root.findtext('result/attributes/charisma')
    character.int_attribute = job.root.findtext('result/attributes/intelligence')
    character.mem_attribute = job.root.findtext('result/attributes/memory')
    character.per_attribute = job.root.findtext('result/attributes/perception')
    character.wil_attribute = job.root.findtext('result/attributes/willpower')
    
    # Update attribute bonuses :ccp:
    enh = job.root.find('result/attributeEnhancers')

    val = enh.find('charismaBonus/augmentatorValue')
    if val is None:
        character.cha_bonus = 0
    else:
        character.cha_bonus = val.text

    val = enh.find('intelligenceBonus/augmentatorValue')
    if val is None:
        character.int_bonus = 0
    else:
        character.int_bonus = val.text

    val = enh.find('memoryBonus/augmentatorValue')
    if val is None:
        character.mem_bonus = 0
    else:
        character.mem_bonus = val.text

    val = enh.find('perceptionBonus/augmentatorValue')
    if val is None:
        character.per_bonus = 0
    else:
        character.per_bonus = val.text

    val = enh.find('willpowerBonus/augmentatorValue')
    if val is None:
        character.wil_bonus = 0
    else:
        character.wil_bonus = val.text

    # Update clone information
    character.clone_skill_points = job.root.findtext('result/cloneSkillPoints')
    character.clone_name = job.root.findtext('result/cloneName')

    # Get all of the rowsets
    rowsets = job.root.findall('result/rowset')
    
    # First rowset is skills
    skills = {}
    for row in rowsets[0]:
        skills[int(row.attrib['typeID'])] = (int(row.attrib['skillpoints']), int(row.attrib['level']))
    
    # Grab any already existing skills
    for char_skill in CharacterSkill.objects.select_related('item', 'skill').filter(character=character, skill__in=skills.keys()):
        points, level = skills[char_skill.skill.item_id]
        if char_skill.points != points or char_skill.level != level:
            char_skill.points = points
            char_skill.level = level
            char_skill.save()
        
        del skills[char_skill.skill.item_id]
    
    # Fetch skill objects
    skill_map = Skill.objects.in_bulk(skills.keys())

    # Add any leftovers
    new = []
    for skill_id, (points, level) in skills.items():
        skill = skill_map.get(skill_id, None)
        if skill is None:
            logger.warn("Skill #%s apparently doesn't exist", skill_id)
            continue

        new.append(CharacterSkill(
            character=character,
            skill=skill,
            points=points,
            level=level,
        ))
    
    # Insert new skills
    if new:
        CharacterSkill.objects.bulk_create(new)

    # Save character
    character.save()
    
    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Fetch contracts
@task
def contracts(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    character = Character.objects.get(pk=character_id)
    
    now = datetime.datetime.now()

    # Initialise for corporate query
    if job.apikey.corp_character:
        params = {}
        c_filter = Contract.objects.filter(
            Q(issuer_corp_id=character.corporation.id) |
            Q(assignee_id=character.corporation.id) |
            Q(acceptor_id=character.corporation.id),
            for_corp=True,
        )
    
    # Initialise for character query
    else:
        params = { 'characterID': character.id }
        c_filter = Contract.objects.filter(
            Q(issuer_char_id=character.id) |
            Q(assignee_id=character.id) |
            Q(acceptor_id=character.id),
            for_corp=False,
        )

    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return


    # Retrieve a list of this user's characters and corporations
    user_chars = list(Character.objects.filter(apikeys__user=job.apikey.user).values_list('id', flat=True))
    user_corps = list(APIKey.objects.filter(user=job.apikey.user).exclude(corp_character=None).values_list('corp_character__corporation__id', flat=True))


    # First we need to get all of the acceptor and assignee IDs
    contract_ids = set()
    station_ids = set()
    lookup_ids = set()
    lookup_corp_ids = set()
    contract_rows = []
    # <row contractID="58108507" issuerID="2004011913" issuerCorpID="751993277" assigneeID="401273477"
    #      acceptorID="0" startStationID="60014917" endStationID="60003760" type="Courier" status="Outstanding"
    #      title="" forCorp="0" availability="Private" dateIssued="2012-08-02 06:50:29" dateExpired="2012-08-09 06:50:29"
    #      dateAccepted="" numDays="7" dateCompleted="" price="0.00" reward="3000000.00" collateral="0.00" buyout="0.00"
    #      volume="10000"/>
    for row in job.root.findall('result/rowset/row'):
        if job.apikey.corp_character:
            # corp keys don't care about non-corp orders
            if row.attrib['forCorp'] == '0':
                continue
            # corp keys don't care about orders they didn't issue - another fun
            # bug where corp keys see alliance contracts they didn't make  :ccp:
            if job.apikey.corp_character.corporation.id not in (int(row.attrib['issuerCorpID']),
                int(row.attrib['assigneeID']), int(row.attrib['acceptorID'])):
                #logger.info('Skipping non-corp contract :ccp:')
                continue

        # non-corp keys don't care about corp orders
        if not job.apikey.corp_character and row.attrib['forCorp'] == '1':
            continue

        contract_ids.add(int(row.attrib['contractID']))
        
        station_ids.add(int(row.attrib['startStationID']))
        station_ids.add(int(row.attrib['endStationID']))

        lookup_ids.add(int(row.attrib['issuerID']))
        lookup_corp_ids.add(int(row.attrib['issuerCorpID']))

        if row.attrib['assigneeID'] != '0':
            lookup_ids.add(int(row.attrib['assigneeID']))
        if row.attrib['acceptorID'] != '0':
            lookup_ids.add(int(row.attrib['acceptorID']))
        
        contract_rows.append(row)

    # Fetch existing chars and corps
    char_map = SimpleCharacter.objects.in_bulk(lookup_ids)
    corp_map = Corporation.objects.in_bulk(lookup_ids | lookup_corp_ids)
    alliance_map = Alliance.objects.in_bulk(lookup_ids)
    
    # Add missing IDs as *UNKNOWN* SimpleCharacters for now
    new = []
    for new_id in lookup_ids.difference(char_map, corp_map, alliance_map, lookup_corp_ids):
        new.append(SimpleCharacter(
            id=new_id,
            name="*UNKNOWN*",
        ))

    if new:
        SimpleCharacter.objects.bulk_create(new)

    # Add missing Corporations too
    new = []
    for new_id in lookup_corp_ids.difference(corp_map):
        new.append(Corporation(
            id=new_id,
            name="*UNKNOWN*",
        ))

    if new:
        Corporation.objects.bulk_create(new)

    # Re-fetch data
    char_map = SimpleCharacter.objects.in_bulk(lookup_ids)
    corp_map = Corporation.objects.in_bulk(lookup_ids | lookup_corp_ids)
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
        
        issuer_char = char_map.get(int(row.attrib['issuerID']), None)
        if issuer_char is None:
            logger.warn('contracts: invalid issuerID %r', row.attrib['issuerID'])
            continue

        issuer_corp = corp_map.get(int(row.attrib['issuerCorpID']), None)
        if issuer_corp is None:
            logger.warn('contracts: invalid issuerCorpID %r', row.attrib['issuerCorpID'])
            continue
        
        assigneeID = int(row.attrib['assigneeID'])
        acceptorID = int(row.attrib['acceptorID'])

        dateIssued = parse_api_date(row.attrib['dateIssued'])
        dateExpired = parse_api_date(row.attrib['dateExpired'])
        
        dateAccepted = row.attrib['dateAccepted']
        if dateAccepted:
            dateAccepted = parse_api_date(dateAccepted)
        else:
            dateAccepted = None

        dateCompleted = row.attrib['dateCompleted']
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
                text = "Contract %s changed status from '%s' to '%s'" % (
                    contract, contract.status, row.attrib['status'])
                
                new_events.append(Event(
                    user_id=job.apikey.user.id,
                    issued=now,
                    text=text,
                ))

                contract.status = row.attrib['status']
                contract.date_accepted = dateAccepted
                contract.date_completed = dateCompleted
                contract.acceptor_id = acceptorID
                contract.save()

        # Contract does not exist, make a new one
        else:
            contract = Contract(
                contract_id=contractID,
                issuer_char=issuer_char,
                issuer_corp=issuer_corp,
                assignee_id=assigneeID,
                acceptor_id=acceptorID,
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
            )
            new_contracts.append(contract)

            # If this contract is a new contract in a non-completed state, log an event
            if contract.status in ('Outstanding', 'InProgress'):
                if assigneeID in user_chars or assigneeID in user_corps:
                    assignee = char_map.get(assigneeID, corp_map.get(assigneeID, alliance_map.get(assigneeID)))
                    if assignee is not None:
                        text = "Contract %s was created from '%s' to '%s' with status '%s'" % (
                            contract, contract.get_issuer_name(), assignee.name, contract.status)
                        
                        new_events.append(Event(
                            user_id=job.apikey.user.id,
                            issued=now,
                            text=text,
                        ))


    # And save the damn things
    Contract.objects.bulk_create(new_contracts)
    Event.objects.bulk_create(new_events)

    
    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Corporation sheet
@task
def corporation_sheet(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return

    params = { 'characterID': job.apikey.corp_character_id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return
    
    corporation = job.apikey.corp_character.corporation
    
    corporation.ticker = job.root.findtext('result/ticker')

    allianceID = job.root.findtext('result/allianceID')
    if allianceID == '0':
        allianceID = None
    corporation.alliance_id = allianceID
    
    errors = 0
    for rowset in job.root.findall('result/rowset'):
        # Divisions
        if rowset.attrib['name'] == 'divisions':
            rows = rowset.findall('row')

            corporation.division1 = rows[0].attrib['description']
            corporation.division2 = rows[1].attrib['description']
            corporation.division3 = rows[2].attrib['description']
            corporation.division4 = rows[3].attrib['description']
            corporation.division5 = rows[4].attrib['description']
            corporation.division6 = rows[5].attrib['description']
            corporation.division7 = rows[6].attrib['description']

        # Wallet divisions
        elif rowset.attrib['name'] == 'walletDivisions':
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
                
                # If it doesn't exist just log an error - we can't create the
                # CorpWallet object without an accountID
                else:
                    logger.warn("No matching CorpWallet object for corpID=%s accountkey=%s", corporation.id, row.attrib['accountKey'])
                    errors += 1

    corporation.save()
    
    # completed ok
    if errors == 0:
        job.completed()
    else:
        job.failed()

# ---------------------------------------------------------------------------
# Locations (and more importantly names) for assets
@task
def locations(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    character = Character.objects.get(pk=character_id)
    
    # Initialise for character query
    if not job.apikey.corp_character:
        a_filter = Asset.objects.root_nodes().filter(character=character, corporation__isnull=True,
            singleton=True, item__item_group__category__name__in=('Celestial', 'Ship'))

    # Get ID list
    ids = map(str, a_filter.values_list('id', flat=True))
    if len(ids) == 0:
        return

    # Fetch the API data
    params = {
        'characterID': character.id,
        'IDs': ','.join(map(str, ids)),
    }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return

    # Build a map of assetID:assetName
    bulk_data = {}
    for row in job.root.findall('result/rowset/row'):
        bulk_data[int(row.attrib['itemID'])] = row.attrib['itemName']

    # Bulk query them
    asset_map = Asset.objects.filter(character=character).in_bulk(bulk_data.keys())

    # Update any new or changed names
    for assetID, assetName in bulk_data.items():
        asset = asset_map.get(assetID, None)
        if asset is not None:
            if asset.name is None or asset.name != assetName:
                asset.name = assetName
                asset.save()
    
    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Market orders
@task
def market_orders(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    character = Character.objects.get(pk=character_id)
    
    # Initialise for corporate key
    if job.apikey.corp_character:
        o_filter = MarketOrder.objects.filter(corp_wallet__corporation=character.corporation)

        wallet_map = {}
        for cw in CorpWallet.objects.filter(corporation=character.corporation):
            wallet_map[cw.account_key] = cw

    # Initialise for other keys
    else:
        o_filter = MarketOrder.objects.filter(corp_wallet=None, character=character)


    # Generate a character id map
    char_id_map = {}
    for char in Character.objects.all():
        char_id_map[char.id] = char
    
    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return
    
    # Generate an order_id map
    order_map = {}
    for mo in o_filter.select_related('item'):
        order_map[mo.order_id] = mo
    
    # Iterate over the returned result set
    new = []
    seen = []
    for row in job.root.findall('result/rowset/row'):
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
        
        # Doesn't exist and is active, make a new order
        elif row.attrib['orderState'] == '0':
            buy_order = (row.attrib['bid'] == '1')
            
            # Make sure the character charID is valid
            char = char_id_map.get(int(row.attrib['charID']))
            if char is None:
                logger.warn("No matching Character object for charID=%s", row.attrib['charID'])
                continue
            
            # Make sure the item typeID is valid
            item = get_item(row.attrib['typeID'])
            if item is None:
                continue
            
            # Create a new order and save it
            remaining = int(row.attrib['volRemaining'])
            price = Decimal(row.attrib['price'])
            issued = parse_api_date(row.attrib['issued'])
            order = MarketOrder(
                order_id=order_id,
                station=get_station(int(row.attrib['stationID'])),
                item=item,
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
            if job.apikey.corp_character:
                #order.corp_wallet = CorpWallet.objects.get(corporation=character.corporation, account_key=row.attrib['accountKey'])
                order.corp_wallet = wallet_map.get(int(row.attrib['accountKey']))

            new.append(order)
            #order.save()
            
            seen.append(order_id)
    

    # Insert any new orders
    if new:
        MarketOrder.objects.bulk_create(new)

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
            user_id=job.apikey.user.id,
            issued=now,
            text=text,
        )
        event.save()

    # Then delete
    to_delete.delete()
    
    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Skill queue
@task
def skill_queue(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    character = Character.objects.get(pk=character_id)

    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return
    
    # Delete the old queue
    SkillQueue.objects.filter(character=character).delete()
    
    # Add new skills
    new = []
    for row in job.root.findall('result/rowset/row'):
        if row.attrib['startTime'] and row.attrib['endTime']:
            new.append(SkillQueue(
                character=character,
                skill_id=row.attrib['typeID'],
                start_time=row.attrib['startTime'],
                end_time=row.attrib['endTime'],
                start_sp=row.attrib['startSP'],
                end_sp=row.attrib['endSP'],
                to_level=row.attrib['level'],
            ))
    
    # Create any new SkillQueue objects
    if new:
        SkillQueue.objects.bulk_create(new)

    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Standings
@task
def standings(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    character = Character.objects.get(pk=character_id)

    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return
    
    # Build data maps
    corp_map = {}
    for cs in CorporationStanding.objects.filter(character=character):
        corp_map[cs.corporation_id] = cs

    faction_map = {}
    for fs in FactionStanding.objects.filter(character=character):
        faction_map[fs.faction_id] = fs

    # Iterate over rowsets
    for rowset in job.root.findall('result/characterNPCStandings/rowset'):
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
                        character_id=character.id,
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
                        character_id=character.id,
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
    job.completed()

# ---------------------------------------------------------------------------
# Fetch wallet transactions
@task
def wallet_transactions(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    character = Character.objects.get(pk=character_id)

    # Corporation key, visit each related CorpWallet
    if job.apikey.corp_character:
        for corpwallet in job.apikey.corp_character.corporation.corpwallet_set.all():
            result = _wallet_transactions_work(url, job, character, corpwallet)
            if result is False:
                job.failed()
                return

    # Account/character key
    else:
        result = _wallet_transactions_work(url, job, character)
        if result is False:
            job.failed()
            return

    job.completed()

# Do the actual work for wallet transactions
def _wallet_transactions_work(url, job, character, corp_wallet=None):
    # Generate a character id map
    char_id_map = {}
    for char in Character.objects.all():
        char_id_map[char.id] = char

    # Initialise stuff
    params = {
        'characterID': character.id,
        'rowCount': TRANSACTION_ROWS,
    }
    
    # Corporation key
    if job.apikey.corp_character:
        params['accountKey'] = corp_wallet.account_key
        t_filter = Transaction.objects.filter(corp_wallet=corp_wallet)
    # Account/Character key
    else:
        t_filter = Transaction.objects.filter(corp_wallet=None, character=character)

    # Loop until we run out of transactions
    cursor = connection.cursor()

    while True:
        if job.fetch_api(url, params) is False or job.root is None:
            return False

        errors = 0
        
        rows = job.root.findall('result/rowset/row')
        # empty result set = no transactions ever on this wallet
        if not rows:
            break
        
        # Make a transaction id:row map
        bulk_data = OrderedDict()
        client_ids = set()
        for row in rows:
            transaction_id = int(row.attrib['transactionID'])
            bulk_data[transaction_id] = row
            client_ids.add(int(row.attrib['clientID']))

        t_map = {}
        for t in t_filter.filter(transaction_id__in=bulk_data.keys()).values('id', 'transaction_id', 'other_char_id', 'other_corp_id'):
            t_map[t['transaction_id']] = t

        # Fetch simplechars and corporations for clients
        simple_map = SimpleCharacter.objects.in_bulk(client_ids)
        corp_map = Corporation.objects.in_bulk(client_ids)
        
        # Now iterate over the leftovers
        new = []
        for transaction_id, row in bulk_data.items():
            transaction_time = parse_api_date(row.attrib['transactionDateTime'])
            
            # Skip corporate transactions if this is a personal call, we have no idea
            # what wallet this transaction is related to otherwise :ccp:
            if row.attrib['transactionFor'].lower() == 'corporation' and not job.apikey.corp_character:
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
                if job.apikey.corp_character:
                    char_id = int(row.attrib['characterID'])
                    char = char_id_map.get(char_id, None)
                    # Doesn't exist, create it
                    if char is None:
                        char = Character(
                            id=char_id,
                            name=row.attrib['characterName'],
                            corporation=job.apikey.corp_character.corporation,
                        )
                        char.save()
                        char_id_map[char_id] = char
                # Any other key = just use the supplied character
                else:
                    char = character
                
                # Create a new transaction object and save it
                quantity = int(row.attrib['quantity'])
                price = Decimal(row.attrib['price'])
                buy_transaction = (row.attrib['transactionType'] == 'buy')

                # Make sure the item typeID is valid
                item = get_item(row.attrib['typeID'])
                if item is None:
                    errors += 1
                    continue

                t = Transaction(
                    station=station,
                    item=item,
                    character=char,
                    transaction_id=transaction_id,
                    date=transaction_time,
                    buy_transaction=buy_transaction,
                    quantity=quantity,
                    price=price,
                    total_price=quantity * price,
                )
                
                # Set the corp_character for corporation API requests
                if job.apikey.corp_character:
                    t.corp_wallet = corp_wallet
                
                # Set whichever client type is relevant
                if isinstance(client, SimpleCharacter):
                    t.other_char_id = client.id
                else:
                    t.other_corp_id = client.id
                
                new.append(t)

            # Transaction exists, check the other_ fields
            else:
                if t['other_char_id'] is None and t['other_corp_id'] is None:
                    if isinstance(client, SimpleCharacter):
                        cursor.execute('UPDATE thing_transaction SET other_char_id = %s WHERE id = %s', (client.id, t['id']))
                    else:
                        cursor.execute('UPDATE thing_transaction SET other_corp_id = %s WHERE id = %s', (client.id, t['id']))
                    
                    logger.info('Updated other_ field of transaction %s', t['id'])
        
        # Create any new transaction objects
        if new:
            Transaction.objects.bulk_create(new)

        # If we got MAX rows we should retrieve some more
        if len(bulk_data) == TRANSACTION_ROWS:
            params['beforeTransID'] = transaction_id
        else:
            break

# ---------------------------------------------------------------------------
# Other periodic tasks
# ---------------------------------------------------------------------------
# Periodic task to update conquerable statio names
CONQUERABLE_STATION_URL = urljoin(settings.API_HOST, '/eve/ConquerableStationList.xml.aspx')

@task
def conquerable_stations():
    r = _session.get(CONQUERABLE_STATION_URL, prefetch=True)
    root = ET.fromstring(r.text)

    # Build a stationID:row dictionary
    bulk_data = {}
    for row in root.findall('result/rowset/row'):
        bulk_data[int(row.attrib['stationID'])] = row

    # Bulk retrieve all of those stations that exist
    data_map = Station.objects.in_bulk(bulk_data.keys())

    new = []
    for id, row in bulk_data.items():
        # If the station already exists...
        station = data_map.get(id, None)
        if station is not None:
            # maybe update the station name
            if station.name != row.attrib['stationName']:
                station.name = row.attrib['stationName']
                station.save()
            continue
        
        # New station!
        new.append(Station(
            id=id,
            name=row.attrib['stationName'],
            system_id=row.attrib['solarSystemID'],
        ))

    # Create any new stations
    if new:
        Station.objects.bulk_create(new)

# ---------------------------------------------------------------------------
# Periodic task to retrieve Jita history data from Goonmetrics
HISTORY_PER_REQUEST = 50
HISTORY_URL = 'http://goonmetrics.com/api/price_history/?region_id=10000002&type_id=%s'

@task
def history_updater():
    # Get a list of all item_ids
    cursor = connection.cursor()
    cursor.execute(queries.all_item_ids)
    
    item_ids = []
    for row in cursor:
        item_ids.append(row[0])

    cursor.close()

    # Collect data
    new = []
    for i in range(0, len(item_ids), 50):
        # Fetch the XML
        url = HISTORY_URL % (','.join(str(z) for z in item_ids[i:i+50]))
        r = _session.get(url, prefetch=True)
        root = ET.fromstring(r.text)
        
        # Do stuff
        for t in root.findall('price_history/type'):
            type_id = int(t.attrib['id'])
            
            data = {}
            for hist in t.findall('history'):
                data[hist.attrib['date']] = hist
            
            # Query that shit
            for ph in PriceHistory.objects.filter(region=10000002, item=type_id, date__in=data.keys()):
                del data[str(ph.date)]
            
            # Add new ones
            for date, hist in data.items():
                new.append(PriceHistory(
                    region_id=10000002,
                    item_id=type_id,
                    date=hist.attrib['date'],
                    minimum=hist.attrib['minPrice'],
                    maximum=hist.attrib['maxPrice'],
                    average=hist.attrib['avgPrice'],
                    movement=hist.attrib['movement'],
                    orders=hist.attrib['numOrders'],
                ))

    if new:
        PriceHistory.objects.bulk_create(new)

# ---------------------------------------------------------------------------
# Periodic task to retrieve current Jita price data from Goonmetrics
PRICE_PER_REQUEST = 100
PRICE_URL = 'http://goonmetrics.com/api/price_data/?station_id=60003760&type_id=%s'

@task
def price_updater():
    # Get a list of all item_ids
    cursor = connection.cursor()
    cursor.execute(queries.all_item_ids)

    item_ids = []
    for row in cursor:
        item_ids.append(row[0])

    cursor.close()

    # Bulk retrieve items
    item_map = Item.objects.in_bulk(item_ids)

    for i in range(0, len(item_ids), PRICE_PER_REQUEST):
        # Retrieve market data and parse the XML
        url = PRICE_URL % (','.join(str(item_id) for item_id in item_ids[i:i+PRICE_PER_REQUEST]))
        r = _session.get(url, prefetch=True)
        root = ET.fromstring(r.text)
        
        # Update item prices
        for t in root.findall('price_data/type'):
            item = item_map[int(t.attrib['id'])]
            item.buy_price = t.find('buy/max').text
            item.sell_price = t.find('sell/min').text
            item.save()

    # Calculate capital ship costs now
    for bp in Blueprint.objects.select_related('item').filter(item__item_group__name__in=('Carrier', 'Dreadnought', 'Supercarrier', 'Titan')):
        bpi = BlueprintInstance(
            user=None,
            blueprint=bp,
            original=True,
            material_level=2,
            productivity_level=0,
        )
        bp.item.sell_price = bpi.calc_capital_production_cost()
        bp.item.save()

# ---------------------------------------------------------------------------
@task
def unknown_characters():
    pass
    # new_chars = []
    # new_corps = []

    # # Go look up all of those names now
    # lookup_map = {}
    # for i in range(0, len(new_ids), 250):
    #     params = { 'ids': ','.join(map(str, new_ids[i:i+250])) }
    #     if job.fetch_api(CHAR_NAME_URL, params, use_auth=False) is False or job.root is None:
    #         logger.warn('uh-oh')
    #         return

    #     # <row name="Tazuki Falorn" characterID="1759080617"/>
    #     for row in job.root.findall('result/rowset/row'):
    #         lookup_map[int(row.attrib['characterID'])] = row.attrib['name']

    # # Ugh, now go look up all of the damn names just in case they're corporations
    # for id, name in lookup_map.items():
    #     params = { 'corporationID': id }
    #     # Not a corporation
    #     if job.fetch_api(CORP_SHEET_URL, params, use_auth=False, log_error=False) is False or job.root is None:
    #         new_chars.append(SimpleCharacter(
    #             id=id,
    #             name=name,
    #         ))
    #     else:
    #         new_corps.append(Corporation(
    #             id=id,
    #             name=name,
    #             ticker=job.root.find('result/ticker').text,
    #         ))

    # # Now we can go create all of those new objects
    # char_map = SimpleCharacter.objects.in_bulk([c.id for c in new_chars])
    # new_chars = [c for c in new_chars if c.id not in char_map]
    # SimpleCharacter.objects.bulk_create(new_chars)

    # corp_map = Corporation.objects.in_bulk([c.id for c in new_corps])
    # new_corps = [c for c in new_corps if c.id not in corp_map]
    # Corporation.objects.bulk_create(new_corps)

# ---------------------------------------------------------------------------
# Parse an API result date into a datetime object
def parse_api_date(s):
    return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')

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
# Caching item fetcher
_item_cache = {}
def get_item(item_id):
    if item_id not in _item_cache:
        try:
            _item_cache[item_id] = Item.objects.get(pk=item_id)
        except Item.DoesNotExist:
            logger.warn("Item #%s apparently doesn't exist", item_id)
            _item_cache[item_id] = None

    return _item_cache[item_id]

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
