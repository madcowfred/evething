import datetime
import requests
import socket
import sys
import time

from decimal import *
from urlparse import urljoin

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from django.conf import settings
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.db import connection, transaction, IntegrityError
from django.db.models import Count, Max

from thing import queries
from thing.models import *

from celery import task
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

from djcelery.models import TaskMeta

# ---------------------------------------------------------------------------
# Requests session
_session = requests.session(
    config={
        'pool_maxsize': 1,
        'max_retries': 0,
    },
    headers={
        'User-Agent': 'EVEthing-tasks (keep-alive)',
    },
)

# ---------------------------------------------------------------------------
# number of rows to request per WalletTransactions call, max is 2560
TRANSACTION_ROWS = 2560

API_KEY_INFO_URL = ('api_key_info', '/account/APIKeyInfo.xml.aspx', 'et_low')

CHAR_URLS = {
    APIKey.CHAR_ACCOUNT_STATUS_MASK: ('account_status', '/account/AccountStatus.xml.aspx', 'et_medium'),
    APIKey.CHAR_ASSET_LIST_MASK: ('asset_list', '/char/AssetList.xml.aspx', 'et_medium'),
    APIKey.CHAR_CHARACTER_SHEET_MASK: ('character_sheet', '/char/CharacterSheet.xml.aspx', 'et_medium'),
    APIKey.CHAR_CONTRACTS_MASK: ('contracts', '/char/Contracts.xml.aspx', 'et_medium'),
    APIKey.CHAR_CHARACTER_INFO_MASK: ('character_info', '/eve/CharacterInfo.xml.aspx', 'et_medium'),
    APIKey.CHAR_INDUSTRY_JOBS_MASK: ('industry_jobs', '/char/IndustryJobs.xml.aspx', 'et_medium'),
    APIKey.CHAR_MARKET_ORDERS_MASK: ('market_orders', '/char/MarketOrders.xml.aspx', 'et_medium'),
    APIKey.CHAR_SKILL_QUEUE_MASK: ('skill_queue', '/char/SkillQueue.xml.aspx', 'et_medium'),
    APIKey.CHAR_STANDINGS_MASK: ('standings', '/char/Standings.xml.aspx', 'et_medium'),
    APIKey.CHAR_WALLET_JOURNAL_MASK: ('wallet_journal', '/char/WalletJournal.xml.aspx', 'et_medium'),
    APIKey.CHAR_WALLET_TRANSACTIONS_MASK: ('wallet_transactions', '/char/WalletTransactions.xml.aspx', 'et_medium'),
}
CORP_URLS = {
    APIKey.CORP_ACCOUNT_BALANCE_MASK: ('account_balance', '/corp/AccountBalance.xml.aspx', 'et_medium'),
    APIKey.CORP_ASSET_LIST_MASK: ('asset_list', '/corp/AssetList.xml.aspx', 'et_medium'),
    APIKey.CORP_CONTRACTS_MASK: ('contracts', '/corp/Contracts.xml.aspx', 'et_medium'),
    APIKey.CORP_CORPORATION_SHEET_MASK: ('corporation_sheet', '/corp/CorporationSheet.xml.aspx', 'et_medium'),
    APIKey.CORP_INDUSTRY_JOBS_MASK: ('industry_jobs', '/corp/IndustryJobs.xml.aspx', 'et_medium'),
    APIKey.CORP_MARKET_ORDERS_MASK: ('market_orders', '/corp/MarketOrders.xml.aspx', 'et_medium'),
    APIKey.CORP_WALLET_JOURNAL_MASK: ('wallet_journal', '/corp/WalletJournal.xml.aspx', 'et_medium'),
    APIKey.CORP_WALLET_TRANSACTIONS_MASK: ('wallet_transactions', '/corp/WalletTransactions.xml.aspx', 'et_medium'),
}

# ---------------------------------------------------------------------------
# Class to wrap things
PENALTY_TIME = 12 * 60 * 60
PENALTY_MULT = 0.2

class APIJob:
    def __init__(self, apikey_id, taskstate_id):
        connection.queries = []
        self.start = time.time()
        self.api_total_time = 0.0

        self.ready = True

        # Fetch APIKey
        try:
            self.apikey = APIKey.objects.select_related('corp_character__corporation', 'user').get(pk=apikey_id)
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
        self.padding = 0

    def completed(self):
        self.apicache.completed()
        self._taskstate_ready()

        if settings.DEBUG:# and False:
            print '%.3fs  %d queries (%.3fs)  API: %.2fs' % (time.time() - self.start,
                len(connection.queries), sum(float(q['time']) for q in connection.queries),
                self.api_total_time
            )
            for query in connection.queries:
                if query['sql'].startswith('INSERT INTO "thing_apicache"'):
                    print '%02.3fs  INSERT INTO "thing_apicache" ...' % (float(query['time']),)
                elif query['sql'].startswith('UPDATE "thing_apicache"'):
                    print '%02.3fs  UPDATE "thing_apicache" ...' % (float(query['time']),)
                else:
                    print '%02.3fs  %s' % (float(query['time']), query['sql'])

    def failed(self):
        self._taskstate_ready()

    def _taskstate_ready(self):
        now = datetime.datetime.now()
        self.taskstate.state = TaskState.READY_STATE
        self.taskstate.mod_time = now

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
        utcnow = datetime.datetime.utcnow()
        params_repr = repr(sorted(params.items()))
        
        # Retrieve the latest APICache object
        apicaches = list(APICache.objects.filter(url=url, parameters=params_repr, cached_until__gt=utcnow).order_by('-cached_until')[:1])
        
        # Data is not cached, fetch new data
        if len(apicaches) == 0:
            apicache = None
            
            # Fetch the URL
            full_url = urljoin(settings.API_HOST, url)
            start = time.time()
            try:
                r = _session.post(full_url, params, prefetch=True)
                data = r.text
            except Exception, e:
                _post_sleep(e)
                return False

            self.api_total_time += (time.time() - start)

            # If the status code is bad return False
            if not r.status_code == requests.codes.ok:
                _post_sleep('Bad status code: %s' % (r.status_code))
                return False

        # Data is cached, use that
        else:
            apicache = apicaches[0]
            data = apicache.text

        # Parse the data if there is any
        if data:
            try:
                self.root = parse_xml(data)
            except ET.ParseError:
                return False

            current = parse_api_date(self.root.find('currentTime').text)
            until = parse_api_date(self.root.find('cachedUntil').text)

            # If the data wasn't cached, cache it now
            if apicache is None:
                # Work out if we need a cache multiplier for this key
                last_seen = APIKey.objects.filter(keyid=self.apikey.keyid, vcode=self.apikey.vcode).aggregate(s=Max('user__userprofile__last_seen'))['s']
                secs = max(0, total_seconds(utcnow - last_seen))
                mult = 1 + (min(20, max(0, secs / PENALTY_TIME)) * PENALTY_MULT)

                # Generate a delta for cache penalty value
                self.padding = max(0, total_seconds(until - current) * mult)
                delta = datetime.timedelta(seconds=self.padding)

                apicache = APICache(
                    url=url,
                    parameters=params_repr,
                    text=data,
                    cached_until=until + delta,
                )
                apicache.save()

            # Check for an error node in the XML
            error = self.root.find('error')
            if error is not None:
                if apicache.error_displayed:
                    return False

                if log_error:
                    logger.error('%s: %s | %s -> %s', error.attrib['code'], error.text, current, until)

                # Permanent key errors
                if error.attrib['code'] in ('202', '203', '204', '205', '210', '211', '212', '207', '220', '222', '223'):
                    now = datetime.datetime.now()

                    # Mark the key as invalid
                    self.apikey.invalidate()

                    # Log an error event for the user
                    text = "Your API key #%d was marked invalid: %s %s" % (self.apikey.id, error.attrib['code'],
                        error.text)
                    Event.objects.create(
                        user_id=self.apikey.user.id,
                        issued=now,
                        text=text,
                    )

                    # Log a key failure
                    fail_reason = '%s: %s' % (error.attrib['code'], error.text)
                    APIKeyFailure.objects.create(
                        user_id=self.apikey.user.id,
                        keyid=self.apikey.keyid,
                        fail_time=now,
                        fail_reason=fail_reason,
                    )

                    # Check if we need to punish this user for their sins
                    one_week_ago = now - datetime.timedelta(7)
                    count = APIKeyFailure.objects.filter(user=self.apikey.user, fail_time__gt=one_week_ago).count()
                    limit = getattr(settings, 'API_FAILURE_LIMIT', 3)
                    if limit > 0 and count >= limit:
                        # Disable their ability to add keys
                        profile = self.apikey.user.get_profile()
                        profile.can_add_keys = False
                        profile.save()

                        # Log that we did so
                        text = "Limit of %d API key failures per 7 days exceeded, you may no longer add keys." % (
                            limit)
                        Event.objects.create(
                            user_id=self.apikey.user.id,
                            issued=now,
                            text=text,
                        )


                apicache.error_displayed = True
                apicache.save()
                
                return False

        self.apicache = apicache

        return True

# helper function to sleep on API failures
def _post_sleep(e):
    # Initialise the cache value
    if cache.get('backoff_count') is None:
        cache.set('backoff_count', 0)
        cache.set('backoff_last', 0)

    now = time.time()
    # if it hasn't been 5 minutes, increment the wait value
    if (now - cache.get('backoff_last')) < 300:
        cache.incr('backoff_count')
    else:
        cache.set('backoff_count', 0)

    cache.set('backoff_last', now)

    sleep_for = 15
    for i in range(cache.get('backoff_count')):
        sleep_for = min(240, sleep_for * 2)

    logger.warn('Sleeping for %d seconds: %s', sleep_for, e)
    time.sleep(sleep_for)

# ---------------------------------------------------------------------------
# Periodic task to clean up broken tasks
@task(ignore_result=True)
def taskstate_cleanup():
    now = datetime.datetime.utcnow()
    fifteen_mins_ago = now - datetime.timedelta(minutes=15)
    four_hours_ago = now - datetime.timedelta(minutes=240)

    # Build a QuerySet to find broken tasks
    taskstates = TaskState.objects.filter(
        # Queued for more than 4 hours?
        Q(state=TaskState.QUEUED_STATE, mod_time__lt=four_hours_ago)
        |
        # Active for more than 15 minutes?
        Q(state=TaskState.ACTIVE_STATE, mod_time__lt=fifteen_mins_ago)
    )

    # FIXME: temp log
    for d in taskstates.values('state', 'url').annotate(n=Count('id')):
        logger.warn('taskstate_cleanup: % 4dx %s', d['n'], d['url'])

    # Set them to restart
    count = taskstates.update(mod_time=now, next_time=now, state=TaskState.READY_STATE)
    if count > 0:
        logger.warn('taskstate_cleanup: reset %d broken tasks', count)

# ---------------------------------------------------------------------------
# Periodic task to clean up expired APICache objects
@task(ignore_result=True)
def apicache_cleanup():
    now = datetime.datetime.utcnow()
    count = APICache.objects.filter(cached_until__lt=now).delete()

# ---------------------------------------------------------------------------
# Periodic task to spawn API tasks
@task(ignore_result=True)
def spawn_tasks():
    now = datetime.datetime.utcnow()
    one_month_ago = now - datetime.timedelta(30)

    # Build a magical QuerySet for APIKey objects
    apikeys = APIKey.objects.select_related('corp_character__corporation')
    apikeys = apikeys.prefetch_related('characters', 'corp_character__corporation__corpwallet_set')
    apikeys = apikeys.filter(valid=True, user__userprofile__last_seen__gt=one_month_ago)

    # Get a set of unique API keys
    keys = {}
    status = {}
    for apikey in apikeys:
        key_info = apikey.get_key_info()
        keys[key_info] = apikey
        status[key_info] = {}

    # Early exit if there's no keys
    if not keys:
        return

    # Check their task states
    for taskstate in TaskState.objects.filter(key_info__in=keys.keys()).iterator():
        status[taskstate.key_info][(taskstate.url, taskstate.parameter)] = taskstate

    # Task data
    taskdata = { True: [], False: [] }
    
    # Iterate over each key, doing stuff
    for key_info, apikey in keys.items():
        masks = apikey.get_masks()
        
        # All keys do keyinfo checks things
        func, url, queue = API_KEY_INFO_URL
        taskstate = status[key_info].get((url, 0), None)

        _init_taskstate(taskdata, now, taskstate, apikey.id, key_info, func, url, queue, 0)


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

                    _init_taskstate(taskdata, now, taskstate, apikey.id, key_info, func, url, queue, parameter)

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

                _init_taskstate(taskdata, now, taskstate, apikey.id, key_info, func, url, queue, character.id)

    # Bulk update the ready ones
    ts_ids = []
    for ts_id, apikey_id, func, url, queue, parameter in taskdata[False]:
        ts_ids.append(ts_id)
        globals()[func].apply_async(
            args=(url, apikey_id, ts_id, parameter),
            queue=queue,
        )
    
    TaskState.objects.filter(pk__in=ts_ids).update(state=TaskState.QUEUED_STATE, mod_time=now)

    # Create the new ones, they can be started next time around
    new = []
    for key_info, apikey_id, func, url, queue, parameter in taskdata[True]:
        new.append(TaskState(
            key_info=key_info,
            url=url,
            parameter=parameter,
            state=TaskState.READY_STATE,
            mod_time=now,
            next_time=now,
        ))
    
    TaskState.objects.bulk_create(new)

def _init_taskstate(taskdata, now, taskstate, apikey_id, key_info, func, url, queue, parameter):
    if taskstate is None:
        taskdata[True].append((key_info, apikey_id, func, url, queue, parameter))
    elif taskstate.queue_now(now):
        taskdata[False].append((taskstate.id, apikey_id, func, url, queue, parameter))

# ---------------------------------------------------------------------------
# Task summaries
@task(ignore_result=True)
def task_summaries():
    cursor = connection.cursor()
    # apparently SQLite doesn't do EXTRACT(), special case it  #BADIDEA
    if 'sqlite' in connection.vendor:
        cursor.execute(queries.task_summary_sqlite)
    else:
        cursor.execute(queries.task_summary_generic)

    # retrieve hourly data from database
    hours = OrderedDict()
    for row in cursor:
        dt = datetime.datetime(int(row[0]), int(row[1]), int(row[2]), int(row[3]))
        hours[dt] = int(row[4])

    # update any current summaries if the count is higher
    first = hours.keys()[0]
    for tsum in TaskSummary.objects.filter(ymdh__gte=first):
        count = hours.get(tsum.ymdh)
        if count is not None:
            if count > tsum.count:
                tsum.count = count
                tsum.save()

            del hours[tsum.ymdh]

    # create new summaries
    new = []
    for ymdh, count in hours.items():
        new.append(TaskSummary(
            ymdh=ymdh,
            count=count,
        ))

    TaskSummary.objects.bulk_create(new)

# ---------------------------------------------------------------------------
# Account balances
@task(ignore_result=True)
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
@task(ignore_result=True)
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
@task(ignore_result=True)
def api_key_info(url, apikey_id, taskstate_id, zero):
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
            
            characters = Character.objects.select_related('config', 'details').filter(id=characterID)
            # Character doesn't exist, make a new one and save it
            if characters.count() == 0:
                character = Character.objects.create(
                    id=characterID,
                    name=row.attrib['characterName'],
                    corporation=corp,
                )

                # Poor error handling
                try:
                    cc = CharacterConfig.objects.create(character=character)
                except:
                    pass
                try:
                    cd = CharacterDetails.objects.create(character=character)
                except:
                    pass

            # Character exists, update API key and corporation information
            else:
                character = characters[0]
                if character.name != row.attrib['characterName'] or character.corporation != corp:
                    character.name = row.attrib['characterName']
                    character.corporation = corp
                    character.save()

                if character.config is None:
                    cc = CharacterConfig.objects.create(character=character)

                if character.details is None:
                    cd = CharacterDetails.objects.create(character=character)
            
            # Save the character
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
LOCATIONS_URL = urljoin(settings.API_HOST, '/char/Locations.xml.aspx')

@task(ignore_result=True)
def asset_list(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    
    try:
        character = Character.objects.get(pk=character_id)
    except Character.DoesNotExist:
        logger.warn("asset_list: Character %s does not exist!", character_id)
        return

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
    data = {
        'assets': [],
        'locations': set(),
        'items': set(),
        'flags': set(),
    }
    _asset_list_recurse(data, job.root.find('result/rowset'), None)

    # Bulk query data
    item_map = Item.objects.in_bulk(data['items'])
    station_map = Station.objects.in_bulk(data['locations'])
    system_map = System.objects.in_bulk(data['locations'])
    flag_map = InventoryFlag.objects.in_bulk(data['flags'])

    # Build new Asset objects for each row
    assets = []
    for asset_id, location_id, container_id, item_id, flag_id, quantity, rawQuantity, singleton in data['assets']:
        item = item_map.get(item_id)
        if item is None:
            logger.warn('asset_list: Invalid item_id %s', item_id)
            continue

        inv_flag = flag_map.get(flag_id)
        if inv_flag is None:
            logger.warn('asset_list: Invalid flag_id %s', flag_id)
            continue

        asset = Asset(
            asset_id=asset_id,
            parent=container_id,
            character=character,
            system=system_map.get(location_id),
            station=station_map.get(location_id),
            item=item,
            inv_flag=inv_flag,
            quantity=quantity,
            raw_quantity=rawQuantity,
            singleton=singleton,
        )
        if job.apikey.corp_character:
            asset.corporation_id = job.apikey.corp_character.corporation.id

        assets.append(asset)

    # Delete existing assets, it's way too painful trying to deal with changes
    a_filter.delete()

    # Bulk insert new assets
    Asset.objects.bulk_create(assets)


    # Fetch names (via Locations API) for assets
    # if job.apikey.corp_character is None and APIKey.CHAR_LOCATIONS_MASK in job.apikey.get_masks():
    #     a_filter = a_filter.filter(singleton=True, item__item_group__category__name__in=('Celestial', 'Ship'))

    #     # Get ID list
    #     ids = map(str, a_filter.values_list('asset_id', flat=True))
    #     if ids:
    #         # Fetch the API data
    #         params['IDs'] = ','.join(map(str, ids))
    #         if job.fetch_api(LOCATIONS_URL, params) is False or job.root is None:
    #             job.completed()
    #             return

    #         # Build a map of assetID:assetName
    #         bulk_data = {}
    #         for row in job.root.findall('result/rowset/row'):
    #             bulk_data[int(row.attrib['itemID'])] = row.attrib['itemName']

    #         # Bulk query them
    #         for asset in a_filter.filter(asset_id__in=bulk_data.keys()):
    #             asset_name = bulk_data.get(asset.asset_id)
    #             if asset.name is None or asset.name != asset_name:
    #                 asset.name = asset_name
    #                 asset.save()

    # completed ok
    job.completed()

# Recursively visit the assets tree and gather data
def _asset_list_recurse(data, rowset, container_id):
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

            data['locations'].add(location_id)

        else:
            location_id = None

        asset_id = int(row.attrib['itemID'])

        item_id = int(row.attrib['typeID'])
        data['items'].add(item_id)

        flag_id = int(row.attrib['flag'])
        data['flags'].add(flag_id)

        data['assets'].append([
            asset_id,
            location_id,
            container_id,
            item_id,
            flag_id,
            int(row.attrib.get('quantity', '0')),
            int(row.attrib.get('rawQuantity', '0')),
            int(row.attrib.get('singleton', '0')),
        ])

        # Now we need to recurse into children rowsets
        for rowset in row.findall('rowset'):
            _asset_list_recurse(data, rowset, asset_id)

# ---------------------------------------------------------------------------
# Character info
@task(ignore_result=True)
def character_info(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    
    try:
        character = Character.objects.select_related('details').get(pk=character_id)
    except Character.DoesNotExist:
        logger.warn("character_info: Character %s does not exist!", character_id)
        return

    # If Character.details doesn't exist, create it now
    if character.details is None:
        character.details = CharacterDetails.objects.create(character=character)

    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return

    # Update character details from the API data
    ship_type_id = job.root.findtext('result/shipTypeID')
    ship_name = job.root.findtext('result/shipName')
    if ship_type_id is not None and ship_type_id.isdigit() and int(ship_type_id) > 0:
        character.details.ship_item_id = ship_type_id
        character.details.ship_name = ship_name or ''
    else:
        character.details.ship_item_id = None
        character.details.ship_name = ''

    character.details.last_known_location = job.root.findtext('result/lastKnownLocation')
    character.details.security_status = job.root.findtext('result/securityStatus')

    # Save the character details
    character.details.save()

    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Character sheet
@task(ignore_result=True)
def character_sheet(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    
    try:
        character = Character.objects.select_related('details').get(pk=character_id)
    except Character.DoesNotExist:
        logger.warn("character_sheet: Character %s does not exist!", character_id)
        return

    # If Character.details doesn't exist, create it now
    if character.details is None:
        character.details = CharacterDetails.objects.create(character=character)

    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return
    
    # Update wallet balance
    character.details.wallet_balance = job.root.findtext('result/balance')
    
    # Update attributes
    character.details.cha_attribute = job.root.findtext('result/attributes/charisma')
    character.details.int_attribute = job.root.findtext('result/attributes/intelligence')
    character.details.mem_attribute = job.root.findtext('result/attributes/memory')
    character.details.per_attribute = job.root.findtext('result/attributes/perception')
    character.details.wil_attribute = job.root.findtext('result/attributes/willpower')
    
    # Update attribute bonuses :ccp:
    enh = job.root.find('result/attributeEnhancers')

    val = enh.find('charismaBonus/augmentatorValue')
    if val is None:
        character.details.cha_bonus = 0
    else:
        character.details.cha_bonus = val.text

    val = enh.find('intelligenceBonus/augmentatorValue')
    if val is None:
        character.details.int_bonus = 0
    else:
        character.details.int_bonus = val.text

    val = enh.find('memoryBonus/augmentatorValue')
    if val is None:
        character.details.mem_bonus = 0
    else:
        character.details.mem_bonus = val.text

    val = enh.find('perceptionBonus/augmentatorValue')
    if val is None:
        character.details.per_bonus = 0
    else:
        character.details.per_bonus = val.text

    val = enh.find('willpowerBonus/augmentatorValue')
    if val is None:
        character.details.wil_bonus = 0
    else:
        character.details.wil_bonus = val.text

    # Update clone information
    character.details.clone_skill_points = job.root.findtext('result/cloneSkillPoints')
    character.details.clone_name = job.root.findtext('result/cloneName')

    # Save character details
    character.details.save()

    # Get all of the rowsets
    rowsets = job.root.findall('result/rowset')
    
    # First rowset is skills
    skills = {}
    for row in rowsets[0]:
        skills[int(row.attrib['typeID'])] = (int(row.attrib['skillpoints']), int(row.attrib['level']))
    
    # Grab any already existing skills
    for char_skill in CharacterSkill.objects.select_related('item', 'skill').filter(character=character, skill__in=skills.keys()):
        skill_id = char_skill.skill.item_id

        # Warn about missing skill IDs
        if skill_id not in skills:
            logger.warn("character_sheet: Character %s had Skill %s go missing", character_id, skill_id)
            char_skill.delete()
            continue

        points, level = skills[skill_id]
        if char_skill.points != points or char_skill.level != level:
            char_skill.points = points
            char_skill.level = level
            char_skill.save()
        
        del skills[skill_id]
    
    # Fetch skill objects
    skill_map = Skill.objects.in_bulk(skills.keys())

    # Add any leftovers
    new = []
    for skill_id, (points, level) in skills.items():
        skill = skill_map.get(skill_id, None)
        if skill is None:
            logger.warn("character_sheet: Skill %s does not exist", skill_id)
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
    #character.save()
    
    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Fetch contracts
@task(ignore_result=True)
def contracts(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    
    try:
        character = Character.objects.get(pk=character_id)
    except Character.DoesNotExist:
        logger.warn("contracts: Character %s does not exist!", character_id)
        return
    
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
    char_map = Character.objects.in_bulk(lookup_ids)
    corp_map = Corporation.objects.in_bulk(lookup_ids | lookup_corp_ids)
    alliance_map = Alliance.objects.in_bulk(lookup_ids)
    
    # Add missing IDs as *UNKNOWN* Characters for now
    new = []
    for new_id in lookup_ids.difference(char_map, corp_map, alliance_map, lookup_corp_ids):
        new.append(Character(
            id=new_id,
            name="*UNKNOWN*",
        ))
        char_map[new_id] = new[-1]

    if new:
        Character.objects.bulk_create(new)

    # Add missing Corporations too
    new = []
    for new_id in lookup_corp_ids.difference(corp_map):
        new.append(Corporation(
            id=new_id,
            name="*UNKNOWN*",
        ))
        corp_map[new_id] = new[-1]

    if new:
        Corporation.objects.bulk_create(new)

    # Re-fetch data
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
            logger.warn('contracts: Invalid issuerID %s', row.attrib['issuerID'])
            continue

        issuer_corp = corp_map.get(int(row.attrib['issuerCorpID']), None)
        if issuer_corp is None:
            logger.warn('contracts: Invalid issuerCorpID %s', row.attrib['issuerCorpID'])
            continue
        
        start_station = station_map.get(int(row.attrib['startStationID']))
        if start_station is None:
            logger.warn('contracts: Invalid startStationID %s', row.attrib['startStationID'])
            continue

        end_station = station_map.get(int(row.attrib['endStationID']))
        if end_station is None:
            logger.warn('contracts: Invalid endStationID %s', row.attrib['endStationID'])
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


    # Force the queryset to update
    c_filter.update()

    # Now go fetch items for each contract
    items_url = url.replace('Contracts', 'ContractItems')
    new = []
    # Apparently courier contracts don't have ContractItems support? :ccp:
    for contract in c_filter.filter(retrieved_items=False).exclude(type='Courier'):
        params['contractID'] = contract.contract_id
        if job.fetch_api(items_url, params) is False or job.root is None:
            job.failed()
            return

        for row in job.root.findall('result/rowset/row'):
            new.append(ContractItem(
                contract_id=contract.contract_id,
                item_id=row.attrib['typeID'],
                quantity=row.attrib['quantity'],
                raw_quantity=row.attrib.get('rawQuantity', 0),
                singleton=row.attrib['singleton'] == '1',
                included=row.attrib['included'] == '1',
            ))

    if new:
        ContractItem.objects.bulk_create(new)
        c_filter.update(retrieved_items=True)
    
    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Corporation sheet
@task(ignore_result=True)
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
                    logger.warn("corporation_sheet: No matching CorpWallet object for Corp %s Account %s", corporation.id, row.attrib['accountKey'])
                    errors += 1

    corporation.save()
    
    # completed ok
    if errors == 0:
        job.completed()
    else:
        job.failed()

# ---------------------------------------------------------------------------
# Industry jobs :cripes:
@task(ignore_result=True)
def industry_jobs(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    
    try:
        character = Character.objects.get(pk=character_id)
    except Character.DoesNotExist:
        logger.warn("industry_jobs: Character %s does not exist!", character_id)
        return

    # Initialise for corporate key
    if job.apikey.corp_character:
        j_filter = IndustryJob.objects.filter(corporation=character.corporation)
    # Initialise for other keys
    else:
        j_filter = IndustryJob.objects.filter(corporation=None, character=character)

    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return

    # Generate a job id map
    job_map = {}
    for ij in j_filter:
        job_map[ij.job_id] = ij
    
    # Iterate over the returned result set
    now = datetime.datetime.now()
    flag_ids = set()
    item_ids = set()
    system_ids = set()

    rows = []
    for row in job.root.findall('result/rowset/row'):
        job_id = int(row.attrib['jobID'])
        
        # Job exists
        ij = job_map.get(job_id, None)
        if ij is not None:
            # Job is still active, update relevant details
            if row.attrib['completed'] == '0':
                install_time = parse_api_date(row.attrib['installTime'])
                begin_time = parse_api_date(row.attrib['beginProductionTime'])
                end_time = parse_api_date(row.attrib['endProductionTime'])
                pause_time = parse_api_date(row.attrib['pauseProductionTime'])

                if install_time > ij.install_time or begin_time > ij.begin_time or end_time > ij.end_time or \
                   pause_time > ij.pause_time:
                    ij.install_time = install_time
                    ij.begin_time = begin_time
                    ij.end_time = end_time
                    ij.pause_time = pause_time
                    ij.save()

            # Job is now complete, issue an event
            elif row.attrib['completed'] and not ij.completed:
                ij.completed = True
                ij.completed_status = row.attrib['completedStatus']
                ij.save()

                text = 'Industry Job #%s (%s, %s) has been delivered' % (ij.job_id, ij.system.name, ij.get_activity_display())
                event = Event(
                    user_id=job.apikey.user.id,
                    issued=now,
                    text=text,
                )
                event.save()

        # Doesn't exist, save data for later
        else:
            flag_ids.add(int(row.attrib['installedItemFlag']))
            flag_ids.add(int(row.attrib['outputFlag']))
            item_ids.add(int(row.attrib['installedItemTypeID']))
            item_ids.add(int(row.attrib['outputTypeID']))
            system_ids.add(int(row.attrib['installedInSolarSystemID']))

            rows.append(row)

    # Bulk query data
    flag_map = InventoryFlag.objects.in_bulk(flag_ids)
    item_map = Item.objects.in_bulk(item_ids)
    system_map = System.objects.in_bulk(system_ids)

    # Create new IndustryJob objects
    new = []
    for row in rows:
        installed_item = item_map.get(int(row.attrib['installedItemTypeID']))
        if installed_item is None:
            logger.warn("industry_jobs: No matching Item %s", row.attrib['installedItemTypeID'])
            continue

        installed_flag = flag_map.get(int(row.attrib['installedItemFlag']))
        if installed_flag is None:
            logger.warn("industry_jobs: No matching InventoryFlag %s", row.attrib['installedItemFlag'])
            continue

        output_item = item_map.get(int(row.attrib['outputTypeID']))
        if output_item is None:
            logger.warn("industry_jobs: No matching Item %s", row.attrib['outputTypeID'])
            continue

        output_flag = flag_map.get(int(row.attrib['outputFlag']))
        if output_flag is None:
            logger.warn("industry_jobs: No matching InventoryFlag %s", row.attrib['outputFlag'])
            continue

        system = system_map.get(int(row.attrib['installedInSolarSystemID']))
        if system is None:
            logger.warn("industry_jobs: No matching System %s", row.attrib['installedInSolarSystemID'])
            continue

        # Create the new job object
        ij = IndustryJob(
            character=character,
            job_id=row.attrib['jobID'],
            assembly_line_id=row.attrib['assemblyLineID'],
            container_id=row.attrib['containerID'],
            location_id=row.attrib['installedItemLocationID'],
            item_productivity_level=row.attrib['installedItemProductivityLevel'],
            item_material_level=row.attrib['installedItemMaterialLevel'],
            licensed_production_runs_remaining=row.attrib['installedItemLicensedProductionRunsRemaining'],
            output_location_id=row.attrib['outputLocationID'],
            installer_id=row.attrib['installerID'],
            runs=row.attrib['runs'],
            licensed_production_runs=row.attrib['licensedProductionRuns'],
            system=system,
            container_location_id=row.attrib['containerLocationID'],
            material_multiplier=row.attrib['materialMultiplier'],
            character_material_multiplier=row.attrib['charMaterialMultiplier'],
            time_multiplier=row.attrib['timeMultiplier'],
            character_time_multiplier=row.attrib['charTimeMultiplier'],
            installed_item=installed_item,
            installed_flag=installed_flag,
            output_item=output_item,
            output_flag=output_flag,
            completed=row.attrib['completed'],
            completed_status=row.attrib['completedStatus'],
            activity=row.attrib['activityID'],
            install_time=parse_api_date(row.attrib['installTime']),
            begin_time=parse_api_date(row.attrib['beginProductionTime']),
            end_time=parse_api_date(row.attrib['endProductionTime']),
            pause_time=parse_api_date(row.attrib['pauseProductionTime']),
        )
        
        if job.apikey.corp_character:
            ij.corporation = job.apikey.corp_character.corporation

        new.append(ij)

    # Insert any new orders
    if new:
        IndustryJob.objects.bulk_create(new)

    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Market orders
@task(ignore_result=True)
def market_orders(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return
    
    try:
        character = Character.objects.get(pk=character_id)
    except Character.DoesNotExist:
        logger.warn("market_orders: Character %s does not exist!", character_id)
        return
    
    # Initialise for corporate key
    if job.apikey.corp_character:
        o_filter = MarketOrder.objects.filter(corp_wallet__corporation=character.corporation)

        wallet_map = {}
        for cw in CorpWallet.objects.filter(corporation=character.corporation):
            wallet_map[cw.account_key] = cw

    # Initialise for other keys
    else:
        o_filter = MarketOrder.objects.filter(corp_wallet=None, character=character)

    o_filter = o_filter.select_related('item')
    
    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return
    
    # Generate an order_id map
    order_map = {}
    for mo in o_filter:
        order_map[mo.order_id] = mo
    
    # Iterate over the returned result set
    char_ids = set()
    item_ids = set()
    station_ids = set()

    rows = []
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

                if issued > order.issued or volRemaining != order.volume_remaining or \
                   escrow != order.escrow or price != order.price:
                    order.issued = issued
                    order.expires = issued + datetime.timedelta(int(row.attrib['duration']))
                    order.volume_remaining = volRemaining
                    order.escrow = escrow
                    order.price = price
                    order.total_price = order.volume_remaining * order.price
                    order.save()
                
                seen.append(order_id)
        
        # Doesn't exist and is active, save data for later
        elif row.attrib['orderState'] == '0':
            char_ids.add(int(row.attrib['charID']))
            item_ids.add(int(row.attrib['typeID']))
            station_ids.add(int(row.attrib['stationID']))

            rows.append(row)
            seen.append(order_id)

    # Bulk query data
    char_map = Character.objects.in_bulk(char_ids)
    item_map = Item.objects.in_bulk(item_ids)
    station_map = Station.objects.in_bulk(station_ids)

    # Create new MarketOrder objects
    new = []
    for row in rows:
        #creator_char = char_map.get(int(row.attrib['charID']))
        #if char is None:
        #    logger.warn("market_orders: No matching Character %s", row.attrib['charID'])
        #    continue

        item = item_map.get(int(row.attrib['typeID']))
        if item is None:
            logger.warn("market_orders: No matching Item %s", row.attrib['typeID'])
            continue

        station = station_map.get(int(row.attrib['stationID']))
        if station is None:
            logger.warn("market_orders: No matching Station %s", row.attrib['stationID'])
            continue

        # Create the new order object
        buy_order = (row.attrib['bid'] == '1')
        remaining = int(row.attrib['volRemaining'])
        price = Decimal(row.attrib['price'])
        issued = parse_api_date(row.attrib['issued'])

        order = MarketOrder(
            order_id=row.attrib['orderID'],
            station=station,
            item=item,
            character=character,
            escrow=Decimal(row.attrib['escrow']),
            creator_character_id=row.attrib['charID'],
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
            order.corp_wallet = wallet_map.get(int(row.attrib['accountKey']))

        new.append(order)

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

        url = '%s?ft=item&fc=eq&fv=%s' % (reverse('thing.views.transactions'), order.item.name)
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
@task(ignore_result=True)
def skill_queue(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return

    try:
        character = Character.objects.get(pk=character_id)
    except Character.DoesNotExist:
        logger.warn("skill_queue: Character %s does not exist!", character_id)
        return

    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return
    
    # Delete the old queue
    SkillQueue.objects.filter(character=character).delete()
    
    # Gather info
    rows = []
    skill_ids = set()
    for row in job.root.findall('result/rowset/row'):
        if row.attrib['startTime'] and row.attrib['endTime']:
            skill_ids.add(int(row.attrib['typeID']))
            rows.append(row)

    skill_map = Skill.objects.in_bulk(skill_ids)

    # Add new skills
    new = []
    for row in rows:
        skill_id = int(row.attrib['typeID'])
        skill = skill_map.get(skill_id)
        if skill is None:
            logger.warn("skill_queue: Skill %s does not exist!", skill_id)
            continue

        new.append(SkillQueue(
            character=character,
            skill=skill,
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
@task(ignore_result=True)
def standings(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return

    try:
        character = Character.objects.get(pk=character_id)
    except Character.DoesNotExist:
        logger.warn("standings: Character %s does not exist!", character_id)
        return

    # Fetch the API data
    params = { 'characterID': character.id }
    if job.fetch_api(url, params) is False or job.root is None:
        job.failed()
        return
    
    # Build data maps
    cs_map = {}
    for cs in CorporationStanding.objects.filter(character=character):
        cs_map[cs.corporation_id] = cs

    fs_map = {}
    for fs in FactionStanding.objects.filter(character=character):
        fs_map[fs.faction_id] = fs

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

                cs = cs_map.get(id, None)
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
            factions = {}
            for row in rowset.findall('row'):
                id = int(row.attrib['fromID'])
                standing = Decimal(row.attrib['standing'])

                fs = fs_map.get(id, None)
                # Standing doesn't exist, make a new one
                if fs is None:
                    factions[id] = (row.attrib['fromName'], standing)
                # Exists, check for standings change
                else:
                    if fs.standing != standing:
                        fs.standing = standing
                        fs.save()

            if factions:
                faction_map = Faction.objects.in_bulk(factions.keys())
                new = []
                for id, (name, standing) in factions.items():
                    if id not in faction_map:
                        Faction.objects.create(
                            id=id,
                            name=name,
                        )

                    new.append(FactionStanding(
                        character_id=character.id,
                        faction_id=id,
                        standing=standing,
                    ))

                if new:
                    FactionStanding.objects.bulk_create(new)

    # completed ok
    job.completed()

# ---------------------------------------------------------------------------
# Fetch wallet journal entries
@task(ignore_result=True)
def wallet_journal(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return

    try:
        character = Character.objects.get(pk=character_id)
    except Character.DoesNotExist:
        logger.warn("wallet_journal: Character %s does not exist!", character_id)
        return

    # Corporation key, visit each related CorpWallet
    if job.apikey.corp_character:
        for corpwallet in job.apikey.corp_character.corporation.corpwallet_set.all():
            result = _wallet_journal_work(url, job, character, corpwallet)
            if result is False:
                job.failed()
                return

            _wjs_work(character, corpwallet)

    # Account/character key
    else:
        result = _wallet_journal_work(url, job, character)
        if result is False:
            job.failed()
            return
            
        _wjs_work(character)

    job.completed()

# Do the actual work for wallet journal entries
def _wallet_journal_work(url, job, character, corp_wallet=None):
    # Initialise stuff
    params = {
        'characterID': character.id,
        'rowCount': TRANSACTION_ROWS,
    }

    # Corporation key
    if job.apikey.corp_character:
        params['accountKey'] = corp_wallet.account_key
        j_filter = JournalEntry.objects.filter(corp_wallet=corp_wallet)
    # Account/Character key
    else:
        j_filter = JournalEntry.objects.filter(corp_wallet=None, character=character)

    # Loop until we run out of entries
    bulk_data = OrderedDict()
    ref_type_ids = set()
    tax_corp_ids = set()
    
    while True:
        if job.fetch_api(url, params) is False or job.root is None:
            return False

        refID = 0
        count = 0
        for row in job.root.findall('result/rowset/row'):
            count += 1

            refID = int(row.attrib['refID'])
            ref_type_ids.add(int(row.attrib['refTypeID']))
            if row.attrib.get('taxReceiverID', ''):
                tax_corp_ids.add(int(row.attrib['taxReceiverID']))

            bulk_data[refID] = row

        if count == TRANSACTION_ROWS:
            params['fromID'] = refID
        else:
            break

    # If we found some data, deal with it
    if bulk_data:
        new_chars = {}

        # Fetch all existing journal entries
        j_map = {}
        for je in j_filter.filter(ref_id__in=bulk_data.keys()):
            j_map[je.ref_id] = je

        # Fetch ref types
        rt_map = RefType.objects.in_bulk(ref_type_ids)

        # Fetch tax corporations
        corp_map = Corporation.objects.in_bulk(tax_corp_ids)

        new = []
        for refID, row in bulk_data.items():
            # Skip JournalEntry objects that we already have
            if refID in j_map:
                continue

            # RefType
            refTypeID = int(row.attrib['refTypeID'])
            ref_type = rt_map.get(refTypeID)
            if ref_type is None:
                logger.warn('wallet_journal: invalid refTypeID #%s', refTypeID)
                continue

            # Tax receiver corporation ID - doesn't exist for /corp/ calls?
            taxReceiverID = row.attrib.get('taxReceiverID', '')
            if taxReceiverID.isdigit():
                trid = int(taxReceiverID)
                tax_corp = corp_map.get(trid)
                if tax_corp is None:
                    if trid not in new_chars:
                        logger.warn('wallet_journal: invalid taxReceiverID #%d', trid)
                        new_chars[trid] = Character(
                            id=trid,
                            name='*UNKNOWN*',
                        )

                    continue
            else:
                tax_corp = None

            # Tax amount - doesn't exist for /corp/ calls?
            taxAmount = row.attrib.get('taxAmount', '')
            if taxAmount:
                tax_amount = Decimal(taxAmount)
            else:
                tax_amount = 0

            # Create the JournalEntry
            je = JournalEntry(
                character=character,
                date=parse_api_date(row.attrib['date']),
                ref_id=refID,
                ref_type=ref_type,
                owner1_id=row.attrib['ownerID1'],
                owner2_id=row.attrib['ownerID2'],
                arg_name=row.attrib['argName1'],
                arg_id=row.attrib['argID1'],
                amount=Decimal(row.attrib['amount']),
                balance=Decimal(row.attrib['balance']),
                reason=row.attrib['reason'],
                tax_corp=tax_corp,
                tax_amount=tax_amount,
            )
            if job.apikey.corp_character:
                je.corp_wallet = corp_wallet

            new.append(je)

        # Now we can add the entries if there are any
        if new:
            JournalEntry.objects.bulk_create(new)

        # Check to see if we need to add any new Character objects
        if new_chars:
            char_map = Character.objects.in_bulk(new_chars.keys())
            insert_me = [v for k, v in new_chars.items() if k not in char_map]
            Character.objects.bulk_create(insert_me)

    return True

# ---------------------------------------------------------------------------

def _wjs_work(character, corp_wallet=None):
    cursor = connection.cursor()

    if corp_wallet is not None:
        cursor.execute(queries.journal_aggregate_corp, (character.id, corp_wallet.account_id))
    else:
        cursor.execute(queries.journal_aggregate_char, (character.id,))

    # Retrieve all current aggregate data
    agg_data = {}
    for js in JournalSummary.objects.filter(character=character, corp_wallet=corp_wallet):
        agg_data[(js.year, js.month, js.day)] = js

    # Check new data
    new = []
    for year, month, day, ref_type_id, total_in, total_out in cursor:
        js = agg_data.get((year, month, day))
        # Doesn't exist, add it later
        if js is None:
            new.append(JournalSummary(
                character=character,
                corp_wallet=corp_wallet,
                year=year,
                month=month,
                day=day,
                ref_type_id=ref_type_id,
                total_in=total_in,
                total_out=total_out,
                balance=total_in + total_out,
            ))
        # Does exist, check for update
        else:
            if js.total_in != total_in or js.total_out != total_out:
                js.total_in = total_in
                js.total_out = total_out
                js.balance = total_in + total_out
                js.save()

    # Create any new summary objects
    JournalSummary.objects.bulk_create(new)

# ---------------------------------------------------------------------------
# Fetch wallet transactions
@task(ignore_result=True)
def wallet_transactions(url, apikey_id, taskstate_id, character_id):
    job = APIJob(apikey_id, taskstate_id)
    if job.ready is False:
        return

    try:
        character = Character.objects.get(pk=character_id)
    except Character.DoesNotExist:
        logger.warn("wallet_transactions: Character %s does not exist!", character_id)
        return

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

    # Stuff to collect
    bulk_data = {}
    char_ids = set()
    item_ids = set()
    station_ids = set()

    # Loop until we run out of transactions
    while True:
        if job.fetch_api(url, params) is False or job.root is None:
            return False
        
        rows = job.root.findall('result/rowset/row')
        # empty result set = no transactions ever on this wallet
        if not rows:
            break
        
        # Gather bulk data
        for row in rows:
            transaction_id = int(row.attrib['transactionID'])
            bulk_data[transaction_id] = row

            char_ids.add(int(row.attrib['clientID']))
            item_ids.add(int(row.attrib['typeID']))
            station_ids.add(int(row.attrib['stationID']))

            if job.apikey.corp_character:
                char_ids.add(int(row.attrib['characterID']))

        # If we got MAX rows we should retrieve some more
        if len(rows) == TRANSACTION_ROWS:
            params['beforeTransID'] = transaction_id
        else:
            break

    # Retrieve any existing transactions
    t_map = {}
    for t in t_filter.filter(transaction_id__in=bulk_data.keys()).values('id', 'transaction_id', 'other_char_id', 'other_corp_id'):
        t_map[t['transaction_id']] = t

    # Fetch bulk data
    char_map = Character.objects.in_bulk(char_ids)
    corp_map = Corporation.objects.in_bulk(char_ids.difference(char_map))
    item_map = Item.objects.in_bulk(item_ids)
    station_map = Station.objects.in_bulk(station_ids)
    
    # Iterate over scary data
    new = []
    for transaction_id, row in bulk_data.items():
        transaction_time = parse_api_date(row.attrib['transactionDateTime'])
        
        # Skip corporate transactions if this is a personal call, we have no idea
        # what CorpWallet this transaction is related to otherwise :ccp:
        if row.attrib['transactionFor'].lower() == 'corporation' and not job.apikey.corp_character:
            continue

        # Handle possible new clients
        client_id = int(row.attrib['clientID'])
        client = char_map.get(client_id, corp_map.get(client_id, None))
        if client is None:
            try:
                client = Character.objects.create(
                    id=client_id,
                    name=row.attrib['clientName'],
                )
            except IntegrityError:
                client = Character.objects.get(id=client_id)

            char_map[client_id] = client

        # Check to see if this transaction already exists
        t = t_map.get(transaction_id, None)
        if t is None:
            # Make sure the item is valid
            item = item_map.get(int(row.attrib['typeID']))
            if item is None:
                logger.warn('wallet_transactions: Invalid item_id %s', row.attrib['typeID'])
                continue

            # Make sure the station is valid
            station = station_map.get(int(row.attrib['stationID']))
            if station is None:
                logger.warn('wallet_transactions: Invalid station_id %s', row.attrib['stationID'])
                continue
            
            # For a corporation key, make sure the character exists
            if job.apikey.corp_character:
                char_id = int(row.attrib['characterID'])
                char = char_map.get(char_id, None)
                # Doesn't exist, create it
                if char is None:
                    char = Character.objects.create(
                        id=char_id,
                        name=row.attrib['characterName'],
                        corporation=job.apikey.corp_character.corporation,
                    )
                    char_map[char_id] = char
            # Any other key = just use the supplied character
            else:
                char = character
            
            # Create a new transaction object and save it
            quantity = int(row.attrib['quantity'])
            price = Decimal(row.attrib['price'])
            buy_transaction = (row.attrib['transactionType'] == 'buy')

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
            if isinstance(client, Character):
                t.other_char_id = client.id
            else:
                t.other_corp_id = client.id
            
            new.append(t)

    # Create any new transaction objects
    if new:
        Transaction.objects.bulk_create(new)

    return True

# ---------------------------------------------------------------------------
# Purge all data related to an APIKey, woo
# ---------------------------------------------------------------------------
@task(ignore_result=True)
def purge_data(apikey_id):
    try:
        apikey = APIKey.objects.get(pk=apikey_id)
    except APIKey.DoesNotExist:
        logger.warn('purge_data: invalid apikey_id %s', apikey_id)
        return

    # Account/Character keys
    now = datetime.datetime.now()
    if apikey.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
        # Get the characters for this key along with a count of related APIKeys
        for char in apikey.characters.annotate(key_count=Count('apikeys')):
            if char.key_count == 1:
                char.delete()
                text = "All data for character '%s' has been purged" % (char.name)
            else:
                text = "All data for character '%s' was not purged due to other API keys referencing it" % (char.name)

            Event.objects.create(
                user_id=apikey.user_id,
                issued=now,
                text=text,
            )

        # Delete the API key if there are no characters remaining
        if apikey.characters.count() == 0:
            apikey.delete()

# ---------------------------------------------------------------------------
# Other periodic tasks
# ---------------------------------------------------------------------------
# Periodic task to update the alliance list and Corporation.alliance fields
ALLIANCE_LIST_URL = urljoin(settings.API_HOST, '/eve/AllianceList.xml.aspx')

@task(ignore_result=True)
def alliance_list():
    try:
        r = _session.get(ALLIANCE_LIST_URL, prefetch=True)
    except Exception, e:
        _post_sleep(e)
        return False

    root = parse_xml(r.text)

    bulk_data = {}
    for row in root.findall('result/rowset/row'):
        bulk_data[int(row.attrib['allianceID'])] = row

    data_map = Alliance.objects.in_bulk(bulk_data.keys())

    new = []
    # <row name="Goonswarm Federation" shortName="CONDI" allianceID="1354830081" executorCorpID="1344654522" memberCount="8960" startDate="2010-06-01 05:36:00"/>
    for id, row in bulk_data.items():
        alliance = data_map.get(id, None)
        if alliance is not None:
            continue

        new.append(Alliance(
            id=id,
            name=row.attrib['name'],
            short_name=row.attrib['shortName'],
        ))

    if new:
        Alliance.objects.bulk_create(new)

    # update any corporations in each alliance
    for id, row in bulk_data.items():
        corp_ids = []
        for corp_row in row.findall('rowset/row'):
            corp_ids.append(int(corp_row.attrib['corporationID']))

        if corp_ids:
            Corporation.objects.filter(pk__in=corp_ids).update(alliance=id)
            Corporation.objects.filter(alliance_id=id).exclude(pk__in=corp_ids).update(alliance=None)

# ---------------------------------------------------------------------------
# Periodic task to update conquerable statio names
CONQUERABLE_STATION_URL = urljoin(settings.API_HOST, '/eve/ConquerableStationList.xml.aspx')

@task(ignore_result=True)
def conquerable_stations():
    try:
        r = _session.get(CONQUERABLE_STATION_URL, prefetch=True)
    except Exception, e:
        _post_sleep(e)
        return False
    root = parse_xml(r.text)

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
        s = Station(
            id=id,
            name=row.attrib['stationName'],
            system_id=row.attrib['solarSystemID'],
        )
        s._make_shorter_name()
        new.append(s)

    # Create any new stations
    if new:
        Station.objects.bulk_create(new)

# ---------------------------------------------------------------------------
# Periodic task to retrieve Jita history data from Goonmetrics
HISTORY_PER_REQUEST = 50
HISTORY_URL = 'http://goonmetrics.com/api/price_history/?region_id=10000002&type_id=%s'

@task(ignore_result=True)
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
        try:
            r = _session.get(url, prefetch=True)
        except Exception, e:
            _post_sleep(e)
            return False
        root = parse_xml(r.text)
        
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

@task(ignore_result=True)
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
        try:
            r = _session.get(url, prefetch=True)
        except Exception, e:
            _post_sleep(e)
            return False
        root = parse_xml(r.text)
        
        # Update item prices
        for t in root.findall('price_data/type'):
            item = item_map[int(t.attrib['id'])]
            item.buy_price = t.find('buy/max').text
            item.sell_price = t.find('sell/min').text
            item.save()

    # Calculate capital ship costs now
    for bp in Blueprint.objects.select_related('item').filter(item__item_group__name__in=('Capital Industrial Ship', 'Carrier', 'Dreadnought', 'Supercarrier', 'Titan')):
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
# Periodic task to try to fix *UNKNOWN* Character objects
CHAR_NAME_URL = urljoin(settings.API_HOST, '/eve/CharacterName.xml.aspx')
CORP_SHEET_URL = urljoin(settings.API_HOST, '/corp/CorporationSheet.xml.aspx')

@task(ignore_result=True)
def fix_unknown_characters():
    # Fetch all unknown Character objects
    char_map = {}
    for char in Character.objects.filter(name='*UNKNOWN*'):
        char_map[char.id] = char
    
    ids = char_map.keys()
    if len(ids) == 0:
        return

    # Go fetch names for them
    name_map = {}
    for i in range(0, len(ids), 250):
        params = { 'ids': ','.join(map(str, ids[i:i+250])) }

        r = _session.post(CHAR_NAME_URL, params, prefetch=True)
        root = parse_xml(r.text)

        error = root.find('error')
        if error is not None:
            logger.warn('fix_unknown_characters: %s', error.text)
            continue

        # <row name="Tazuki Falorn" characterID="1759080617"/>
        for row in root.findall('result/rowset/row'):
            name_map[int(row.attrib['characterID'])] = row.attrib['name']

    if len(name_map) == 0:
        return

    # Ugh, now go look up all of the damn names just in case they're corporations
    new_corps = []
    for id, name in name_map.items():
        params = { 'corporationID': id }
        r = _session.post(CORP_SHEET_URL, params, prefetch=True)
        root = parse_xml(r.text)

        error = root.find('error')
        if error is not None:
            # Not a corporation, update the Character object
            char = char_map.get(id)
            char.name = name
            char.save()
        else:
            new_corps.append(Corporation(
                id=id,
                name=name,
                ticker=root.find('result/ticker').text,
            ))

    # Now we can create the new corporation objects
    corp_map = Corporation.objects.in_bulk([c.id for c in new_corps])
    new_corps = [c for c in new_corps if c.id not in corp_map]
    Corporation.objects.bulk_create(new_corps)

    # And finally delete all of the things we probably added
    Character.objects.filter(pk__in=name_map.keys(), name='*UNKNOWN*').delete()

# ---------------------------------------------------------------------------
# Parse data into an XML ElementTree
def parse_xml(data):
    return ET.fromstring(data.encode('utf-8'))

# ---------------------------------------------------------------------------
# Parse an API result date into a datetime object
def parse_api_date(s):
    return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')

# ---------------------------------------------------------------------------
# Corporation fetcher, adds new corporations to the database
def get_corporation(corp_id, corp_name):
    corp, created = Corporation.objects.get_or_create(pk=corp_id, defaults={ 'name': corp_name })
    return corp
