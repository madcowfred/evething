import os
import sys

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
