import datetime
import os
import sys

from celery import task
from celery.execute import send_task

from thing.models import APIKey, TaskState

# ---------------------------------------------------------------------------

API_KEY_INFO_URL = ('thing.api_key_info', '/account/APIKeyInfo.xml.aspx', 'et_low')

CHAR_URLS = {
    APIKey.CHAR_ACCOUNT_STATUS_MASK: ('thing.account_status', '/account/AccountStatus.xml.aspx', 'et_medium'),
    # APIKey.CHAR_ASSET_LIST_MASK: ('thing.asset_list', '/char/AssetList.xml.aspx', 'et_medium'),
    APIKey.CHAR_CHARACTER_INFO_MASK: ('thing.character_info', '/eve/CharacterInfo.xml.aspx', 'et_medium'),
    APIKey.CHAR_CHARACTER_SHEET_MASK: ('thing.character_sheet', '/char/CharacterSheet.xml.aspx', 'et_medium'),
    # APIKey.CHAR_CONTRACTS_MASK: ('thing.contracts', '/char/Contracts.xml.aspx', 'et_medium'),
    # APIKey.CHAR_INDUSTRY_JOBS_MASK: ('thing.industry_jobs', '/char/IndustryJobs.xml.aspx', 'et_medium'),
    # APIKey.CHAR_MARKET_ORDERS_MASK: ('thing.market_orders', '/char/MarketOrders.xml.aspx', 'et_medium'),
    APIKey.CHAR_SKILL_QUEUE_MASK: ('thing.skill_queue', '/char/SkillQueue.xml.aspx', 'et_medium'),
    APIKey.CHAR_STANDINGS_MASK: ('thing.standings', '/char/Standings.xml.aspx', 'et_medium'),
    # APIKey.CHAR_WALLET_JOURNAL_MASK: ('thing.wallet_journal', '/char/WalletJournal.xml.aspx', 'et_medium'),
    # APIKey.CHAR_WALLET_TRANSACTIONS_MASK: ('thing.wallet_transactions', '/char/WalletTransactions.xml.aspx', 'et_medium'),
}

CORP_URLS = {
    APIKey.CORP_ACCOUNT_BALANCE_MASK: ('thing.account_balance', '/corp/AccountBalance.xml.aspx', 'et_medium'),
    # APIKey.CORP_ASSET_LIST_MASK: ('thing.asset_list', '/corp/AssetList.xml.aspx'),
    # APIKey.CORP_CONTRACTS_MASK: ('thing.contracts', '/corp/Contracts.xml.aspx'),
    APIKey.CORP_CORPORATION_SHEET_MASK: ('thing.corporation_sheet', '/corp/CorporationSheet.xml.aspx', 'et_medium'),
    # APIKey.CORP_INDUSTRY_JOBS_MASK: ('thing.industry_jobs', '/corp/IndustryJobs.xml.aspx'),
    # APIKey.CORP_MARKET_ORDERS_MASK: ('thing.market_orders', '/corp/MarketOrders.xml.aspx'),
    # APIKey.CORP_MEMBER_TRACKING_MASK: ('thing.member_tracking', '/corp/MemberTracking.xml.aspx'),
    # APIKey.CORP_OUTPOST_LIST_MASK: ('outpost_list', '/corp/OutpostList.xml.aspx'),
    # APIKey.CORP_SHAREHOLDERS_MASK: ('thing.shareholders', '/corp/Shareholders.xml.aspx'),
    # APIKey.CORP_WALLET_JOURNAL_MASK: ('thing.wallet_journal', '/corp/WalletJournal.xml.aspx'),
    # APIKey.CORP_WALLET_TRANSACTIONS_MASK: ('thing.wallet_transactions', '/corp/WalletTransactions.xml.aspx'),
}

GLOBAL_TASKS = (
    ('thing.alliance_list', '/eve/AllianceList.xml.aspx', 'et_medium'),
    ('thing.conquerable_station_list', '/eve/ConquerableStationList.xml.aspx', 'et_medium'),
    ('thing.ref_types', '/eve/RefTypes.xml.aspx', 'et_medium'),
)

# ---------------------------------------------------------------------------
# Periodic task to spawn API tasks
@task(name='thing.task_spawner')
def task_spawner():
    now = datetime.datetime.utcnow()
    one_month_ago = now - datetime.timedelta(30)

    # Task data
    taskdata = { 'new': [], 'ready': [] }


    # Global API tasks
    g_tasks = {}
    for taskstate in TaskState.objects.filter(keyid=-1):
        g_tasks[taskstate.url] = taskstate

    for taskname, url, queue in GLOBAL_TASKS:
        taskstate = g_tasks.get(url)
        _init_taskstate(taskdata, now, taskstate, -1, None, taskname, url, queue, 0)


    # Build a magical QuerySet for APIKey objects
    apikeys = APIKey.objects.select_related('corp_character__corporation')
    apikeys = apikeys.prefetch_related('characters', 'corp_character__corporation__corpwallet_set')
    apikeys = apikeys.filter(valid=True, user__userprofile__last_seen__gt=one_month_ago)

    # Get a set of unique API keys
    keys = {}
    status = {}
    for apikey in apikeys:
        keys[apikey.keyid] = apikey
        status[apikey.keyid] = {}

    # Early exit if there are no valid keys
    if len(keys) == 0:
        return

    # Check their task states
    for taskstate in TaskState.objects.filter(keyid__in=keys.keys()).iterator():
        status[taskstate.keyid][(taskstate.url, taskstate.parameter)] = taskstate

    # Iterate over each key, doing stuff
    for keyid, apikey in keys.items():
        masks = apikey.get_masks()
        
        # All keys do keyinfo checks things
        func, url, queue = API_KEY_INFO_URL
        taskstate = status[keyid].get((url, 0), None)

        _init_taskstate(taskdata, now, taskstate, keyid, apikey.id, func, url, queue, 0)

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

                    taskstate = status[keyid].get((url, parameter), None)

                    _init_taskstate(taskdata, now, taskstate, keyid, apikey.id, func, url, queue, parameter)

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

                taskstate = status[keyid].get((url, character.id), None)

                _init_taskstate(taskdata, now, taskstate, keyid, apikey.id, func, url, queue, character.id)

    # Bulk update the ready ones
    ts_ids = []
    for ts_id, apikey_id, func, url, queue, parameter in taskdata['ready']:
        ts_ids.append(ts_id)
        send_task(
            func,
            args=(url, ts_id, apikey_id, parameter),
            kwargs={},
            queue=queue,
        )
    
    TaskState.objects.filter(pk__in=ts_ids).update(state=TaskState.QUEUED_STATE, mod_time=now)

    # Create the new ones, they can be started next time around
    new = []
    for keyid, func, url, parameter in taskdata['new']:
        new.append(TaskState(
            keyid=keyid,
            url=url,
            parameter=parameter,
            state=TaskState.READY_STATE,
            mod_time=now,
            next_time=now,
        ))
    
    TaskState.objects.bulk_create(new)

# ---------------------------------------------------------------------------
# apikey_id: the 'id' column of the APIKey object
# keyid    : the 'keyid' column of the APIKey object
def _init_taskstate(taskdata, now, taskstate, keyid, apikey_id, func, url, queue, parameter):
    if taskstate is None:
        taskdata['new'].append((keyid, func, url, parameter))
    elif taskstate.queue_now(now):
        taskdata['ready'].append((taskstate.id, apikey_id, func, url, queue, parameter))

# ---------------------------------------------------------------------------
