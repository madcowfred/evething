# ------------------------------------------------------------------------------
# Copyright (c) 2010-2013, EVEthing team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     Redistributions of source code must retain the above copyright notice, this
#       list of conditions and the following disclaimer.
#     Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
# ------------------------------------------------------------------------------

import datetime

from celery import task
from celery.execute import send_task

from thing.models import APIKey, TaskState

# ---------------------------------------------------------------------------

API_KEY_INFO_URL = ('thing.api_key_info', '/account/APIKeyInfo.xml.aspx', 'et_low')

CHAR_URLS = {
    APIKey.CHAR_ACCOUNT_STATUS_MASK: [('thing.account_status', '/account/AccountStatus.xml.aspx', 'et_medium')],
    APIKey.CHAR_ASSET_LIST_MASK: [
        ('thing.asset_list', '/char/AssetList.xml.aspx', 'et_medium'),
        ('thing.planetary_colonies', '/char/PlanetaryColonies.xml.aspx', 'et_medium')
    ],
    APIKey.CHAR_CHARACTER_INFO_MASK: [('thing.character_info', '/eve/CharacterInfo.xml.aspx', 'et_medium')],
    APIKey.CHAR_CHARACTER_SHEET_MASK: [('thing.character_sheet', '/char/CharacterSheet.xml.aspx', 'et_medium')],
    APIKey.CHAR_CONTRACTS_MASK: [('thing.contracts', '/char/Contracts.xml.aspx', 'et_medium')],
    APIKey.CHAR_INDUSTRY_JOBS_MASK: [('thing.industry_jobs', '/char/IndustryJobsHistory.xml.aspx', 'et_medium')],
    APIKey.CHAR_MAILING_LISTS_MASK: [('thing.mailing_lists', '/char/MailingLists.xml.aspx', 'et_medium')],
    APIKey.CHAR_MAIL_MESSAGES_MASK: [('thing.mail_messages', '/char/MailMessages.xml.aspx', 'et_medium')],
    APIKey.CHAR_MARKET_ORDERS_MASK: [('thing.market_orders', '/char/MarketOrders.xml.aspx', 'et_medium')],
    APIKey.CHAR_SKILL_QUEUE_MASK: [('thing.skill_queue', '/char/SkillQueue.xml.aspx', 'et_medium')],
    APIKey.CHAR_STANDINGS_MASK: [('thing.standings', '/char/Standings.xml.aspx', 'et_medium')],
    APIKey.CHAR_WALLET_JOURNAL_MASK: [('thing.wallet_journal', '/char/WalletJournal.xml.aspx', 'et_medium')],
    APIKey.CHAR_WALLET_TRANSACTIONS_MASK: [('thing.wallet_transactions', '/char/WalletTransactions.xml.aspx', 'et_medium')],
}

CORP_URLS = {
    APIKey.CORP_ACCOUNT_BALANCE_MASK: ('thing.account_balance', '/corp/AccountBalance.xml.aspx', 'et_medium'),
    APIKey.CORP_ASSET_LIST_MASK: ('thing.asset_list', '/corp/AssetList.xml.aspx', 'et_medium'),
    APIKey.CORP_CONTRACTS_MASK: ('thing.contracts', '/corp/Contracts.xml.aspx', 'et_medium'),
    APIKey.CORP_CORPORATION_SHEET_MASK: ('thing.corporation_sheet', '/corp/CorporationSheet.xml.aspx', 'et_medium'),
    APIKey.CORP_INDUSTRY_JOBS_MASK: ('thing.industry_jobs', '/corp/IndustryJobsHistory.xml.aspx', 'et_medium'),
    APIKey.CORP_MARKET_ORDERS_MASK: ('thing.market_orders', '/corp/MarketOrders.xml.aspx', 'et_medium'),
    APIKey.CORP_WALLET_JOURNAL_MASK: ('thing.wallet_journal', '/corp/WalletJournal.xml.aspx', 'et_medium'),
    APIKey.CORP_WALLET_TRANSACTIONS_MASK: ('thing.wallet_transactions', '/corp/WalletTransactions.xml.aspx', 'et_medium'),
}
# APIKey.CORP_MEMBER_TRACKING_MASK: ('thing.member_tracking', '/corp/MemberTracking.xml.aspx', 'et_medium'),
# APIKey.CORP_OUTPOST_LIST_MASK: ('outpost_list', '/corp/OutpostList.xml.aspx', 'et_medium'),
# APIKey.CORP_SHAREHOLDERS_MASK: ('thing.shareholders', '/corp/Shareholders.xml.aspx', 'et_medium'),

GLOBAL_TASKS = (
    ('thing.alliance_list', '/eve/AllianceList.xml.aspx', 'et_medium'),
    ('thing.conquerable_station_list', '/eve/ConquerableStationList.xml.aspx', 'et_medium'),
    ('thing.ref_types', '/eve/RefTypes.xml.aspx', 'et_medium'),
    ('thing.server_status', '/server/ServerStatus.xml.aspx', 'et_high'),
)


@task(name='thing.task_spawner')
def task_spawner():
    """Periodic task to spawn API tasks"""
    now = datetime.datetime.utcnow()
    one_month_ago = now - datetime.timedelta(30)

    # Task data
    taskdata = {'new': [], 'ready': []}

    # Global API tasks
    g_tasks = {}
    for taskstate in TaskState.objects.filter(keyid=-1):
        g_tasks[taskstate.url] = taskstate

    for taskname, url, queue in GLOBAL_TASKS:
        taskstate = g_tasks.get(url)
        _init_taskstate(taskdata, now, taskstate, -1, None, taskname, url, queue, 0)

    # Build a magical QuerySet for APIKey objects
    apikeys = APIKey.objects.select_related('corporation')
    apikeys = apikeys.prefetch_related('characters', 'corporation__corpwallet_set')
    apikeys = apikeys.filter(valid=True, user__profile__last_seen__gt=one_month_ago)

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

        # Don't do anything else if this key needs APIKeyInfo
        if apikey.needs_apikeyinfo:
            continue

        # Account/character keys
        if apikey.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
            for mask in masks:
                # get useful URL data for this mask
                url_datas = CHAR_URLS.get(mask, None)
                if url_datas is None:
                    continue

                for url_data in url_datas:
                    func, url, queue = url_data

                    for character in apikey.characters.all():
                        if mask == APIKey.CHAR_ACCOUNT_STATUS_MASK and func == 'thing.account_status':
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


def _init_taskstate(taskdata, now, taskstate, keyid, apikey_id, func, url, queue, parameter):
    """
        apikey_id: the 'id' column of the APIKey object
        keyid    : the 'keyid' column of the APIKey object
    """
    if taskstate is None:
        taskdata['new'].append((keyid, func, url, parameter))
    elif taskstate.queue_now(now):
        taskdata['ready'].append((taskstate.id, apikey_id, func, url, queue, parameter))

# ---------------------------------------------------------------------------
