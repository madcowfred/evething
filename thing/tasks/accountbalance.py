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

from decimal import *

from .apitask import APITask

from thing.models import CorpWallet

# ---------------------------------------------------------------------------

class AccountBalance(APITask):
    name = 'thing.account_balance'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return

        params = { 'characterID': character_id }
        if self.fetch_api(url, params) is False or self.root is None:
            return

        corporation = self.apikey.corp_character.corporation

        wallet_map = {}
        for cw in corporation.corpwallet_set.all():
            wallet_map[cw.account_key] = cw

        new = []
        for row in self.root.findall('result/rowset/row'):
            accountID = int(row.attrib['accountID'])
            accountKey = int(row.attrib['accountKey'])
            balance = Decimal(row.attrib['balance'])

            wallet = wallet_map.get(accountKey, None)

            # Wallet doesn't exist, create it
            if wallet is None:
                new.append(CorpWallet(
                    corporation=corporation,
                    account_id=accountID,
                    account_key=accountKey,
                    description='',
                    balance=balance,
                ))
            # Division does exist and the balance has changed, update it
            elif wallet.balance != balance:
                wallet.balance = balance
                wallet.save()

        # Create any new CorporationWallet objects
        if new:
            CorpWallet.objects.bulk_create(new)

        return True

# ---------------------------------------------------------------------------
