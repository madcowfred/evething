import datetime
import requests
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
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

# ---------------------------------------------------------------------------

HEADERS = {
    'User-Agent': 'EVEthing-tasks',
}

API_KEY_INFO_URL = ('api_key_info', '/account/APIKeyInfo.xml.aspx', 'et_low')

CHAR_URLS = {
    APIKey.CHAR_ACCOUNT_STATUS_MASK: ('account_status', '/account/AccountStatus.xml.aspx', 'et_medium'),
    APIKey.CHAR_CHARACTER_SHEET_MASK: ('character_sheet', '/char/CharacterSheet.xml.aspx', 'et_medium'),
}

# ---------------------------------------------------------------------------
# Class to wrap things
class APIJob:
    def __init__(self, apikey_id, taskstate_id):
        self.apikey = APIKey.objects.get(pk=apikey_id)
        self.taskstate = TaskState.objects.get(pk=taskstate_id)
        #self.parameter_id = parameter_id

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
            self.taskstate.next_time = now + datetime.timedelta(seconds=30)

        self.taskstate.save()

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
            #logger.info('Fetching URL %s', full_url)

            # Fetch the URL
            #start = time.time()
            
            r = requests.post(full_url, params, headers=HEADERS, config={ 'max_retries': 1 })
            data = r.text
            
            #duration = time.time() - start
            #self.api_total_time += duration
            #logger.info('URL retrieved in %.2fs', duration)

            # If the status code is bad return False
            if not r.status_code == requests.codes.ok:
                return False

        # Data is cached, use that
        else:
            #logger.info('Cached URL %s', url)
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
                    logger.error('(%s) %s: %s | %s -> %s', self.__class__.__name__, error.attrib['code'], error.text, current, until)

                # Mark key as invalid if it's an auth error
                if error.attrib['code'] in ('202', '203', '204', '205', '210', '212', '207', '220', '222', '223'):
                    self.apikey.valid = False
                    self.apikey.save()
                
                apicache.error_displayed = True
                apicache.save()
                
                return False

        self.apicache = apicache

        return True


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

        # If task isn't found, make a new taskstate and queue the task
        if taskstate is None:
            taskstate = TaskState.objects.create(
                key_info=key_info,
                url=url,
                parameter=0,
                state=TaskState.QUEUED_STATE,
                mod_time=now,
                next_time=now,
            )

            start = True

        else:
            start = taskstate.queue_now(now)

        # If we need to queue this task, do so
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

                    else:
                        start = taskstate.queue_now(now)

                    # If we need to queue this task, do so
                    if start is True:
                        f = globals()[func]
                        f.apply_async(
                            args=(url, apikey.id, taskstate.id, parameter),
                            queue=queue,
                        )

                    # Only do account status once per key
                    if mask == APIKey.CHAR_ACCOUNT_STATUS_MASK:
                        break

# ---------------------------------------------------------------------------
# Account status
@task
def account_status(url, apikey_id, taskstate_id, zero):
    job = APIJob(apikey_id, taskstate_id)

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
# Update character sheet
@task
def character_sheet(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
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
            logging.warn("Skill #%s apparently doesn't exist", skill_id)
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
        r = requests.get(url, headers=HEADERS)
        root = ET.fromstring(r.text)
        
        # Update item prices
        for t in root.findall('price_data/type'):
            item = item_map[int(t.attrib['id'])]
            item.buy_price = t.find('buy/max').text
            item.sell_price = t.find('sell/min').text
            item.save()

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
        r = requests.get(url, headers=HEADERS)
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
