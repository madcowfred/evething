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

from django.contrib.auth.models import User
from django.db import models

from celery.execute import send_task

from core.util import total_seconds

from thing.models.character import Character
from thing.models.corporation import Corporation

# ------------------------------------------------------------------------------
# API keys
class APIKey(models.Model):
    ACCOUNT_TYPE = 'Account'
    CHARACTER_TYPE = 'Character'
    CORPORATION_TYPE = 'Corporation'

    API_KEY_INFO_MASK = 0

    CHAR_ACCOUNT_STATUS_MASK = 33554432
    CHAR_ASSET_LIST_MASK = 2
    CHAR_CHARACTER_INFO_MASK = 16777216
    CHAR_CHARACTER_SHEET_MASK = 8
    CHAR_CONTRACTS_MASK = 67108864
    CHAR_INDUSTRY_JOBS_MASK = 128
    CHAR_LOCATIONS_MASK = 134217728
    CHAR_MAIL_BODIES_MASK = 512
    CHAR_MAILING_LISTS_MASK = 1024
    CHAR_MAIL_MESSAGES_MASK = 2048
    CHAR_MARKET_ORDERS_MASK = 4096
    CHAR_SKILL_QUEUE_MASK = 262144
    CHAR_STANDINGS_MASK = 524288
    CHAR_WALLET_JOURNAL_MASK = 2097152
    CHAR_WALLET_TRANSACTIONS_MASK = 4194304

    MASKS_CHAR = (
        CHAR_ACCOUNT_STATUS_MASK,
        CHAR_ASSET_LIST_MASK,
        CHAR_CHARACTER_INFO_MASK,
        CHAR_CHARACTER_SHEET_MASK,
        CHAR_CONTRACTS_MASK,
        CHAR_INDUSTRY_JOBS_MASK,
        CHAR_LOCATIONS_MASK,
        CHAR_MAIL_MESSAGES_MASK,
        CHAR_MAILING_LISTS_MASK,
        CHAR_MARKET_ORDERS_MASK,
        CHAR_SKILL_QUEUE_MASK,
        CHAR_STANDINGS_MASK,
        CHAR_WALLET_JOURNAL_MASK,
        CHAR_WALLET_TRANSACTIONS_MASK,
    )

    CORP_ACCOUNT_BALANCE_MASK = 1
    CORP_ASSET_LIST_MASK = 2
    CORP_CONTRACTS_MASK = 8388608
    CORP_CORPORATION_SHEET_MASK = 8
    CORP_INDUSTRY_JOBS_MASK = 128
    CORP_MARKET_ORDERS_MASK = 4096
    CORP_WALLET_JOURNAL_MASK = 1048576
    CORP_WALLET_TRANSACTIONS_MASK = 2097152

    MASKS_CORP = (
        CORP_ACCOUNT_BALANCE_MASK,
        CORP_ASSET_LIST_MASK,
        CORP_CONTRACTS_MASK,
        CORP_CORPORATION_SHEET_MASK,
        CORP_INDUSTRY_JOBS_MASK,
        CORP_MARKET_ORDERS_MASK,
        CORP_WALLET_JOURNAL_MASK,
        CORP_WALLET_TRANSACTIONS_MASK,
    )

    user = models.ForeignKey(User)

    keyid = models.IntegerField(verbose_name='Key ID', db_index=True)
    vcode = models.CharField(max_length=64, verbose_name='Verification code')
    access_mask = models.BigIntegerField(default=0)
    override_mask = models.BigIntegerField(default=0)
    key_type = models.CharField(max_length=16, default='')
    expires = models.DateTimeField(null=True, blank=True)
    paid_until = models.DateTimeField(null=True, blank=True)

    name = models.CharField(max_length=64, default='')
    group_name = models.CharField(max_length=32, default='')

    created_at = models.DateTimeField(auto_now=True)

    valid = models.BooleanField(default=True)
    needs_apikeyinfo = models.BooleanField(default=False)
    apikeyinfo_errors = models.IntegerField(default=0)

    characters = models.ManyToManyField(Character, related_name='apikeys')

    # this is only used for corporate keys, ugh
    corp_character = models.ForeignKey(Character, null=True, blank=True, related_name='corporate_apikey')
    corporation = models.ForeignKey(Corporation, null=True, blank=True)

    class Meta:
        app_label = 'thing'
        ordering = ('keyid',)

    def __unicode__(self):
        return '#%s, keyId: %s (%s)' % (self.id, self.keyid, self.key_type)

    def get_masked_vcode(self):
        return '%s%s%s' % (self.vcode[:4], '*' * 16, self.vcode[-4:])

    def get_remaining_time(self):
        if self.paid_until:
            return max(total_seconds(self.paid_until - datetime.datetime.utcnow()), 0)
        else:
            return 0

    def get_masks(self):
        if self.access_mask == 0:
            return []
        elif self.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
            if self.override_mask > 0:
                return [mask for mask in self.MASKS_CHAR if self.override_mask & mask == mask]
            else:
                return [mask for mask in self.MASKS_CHAR if self.access_mask & mask == mask]
        elif self.key_type == APIKey.CORPORATION_TYPE:
            if self.override_mask > 0:
                return [mask for mask in self.MASKS_CORP if self.override_mask & mask == mask]
            else:
                return [mask for mask in self.MASKS_CORP if self.access_mask & mask == mask]
        else:
            return []

    # Mark this key as invalid
    def invalidate(self):
        self.valid = False
        self.save()

    # Delete ALL related data for this key
    def purge_data(self):
        self.invalidate()

        send_task('thing.purge_api_key', args=[self.id], kwargs={}, queue='et_high')

# ------------------------------------------------------------------------------
