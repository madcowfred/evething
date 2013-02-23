import os
import sys

from .apitask import APITask

# need to import model definitions from frontend
from thing.models import CorpWallet

# ---------------------------------------------------------------------------

class CorporationSheet(APITask):
    name = 'thing.corporation_sheet'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Fetch the API data
        params = { 'characterID': character_id }
        if self.fetch_api(url, params) is False or self.root is None:
            return

        corporation = self.apikey.corp_character.corporation
        
        corporation.ticker = self.root.findtext('result/ticker')

        allianceID = self.root.findtext('result/allianceID')
        if allianceID == '0':
            allianceID = None
        corporation.alliance_id = allianceID

        for rowset in self.root.findall('result/rowset'):
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
                    wallet = wallet_map.get(int(row.attrib['accountKey']))
                    
                    # If the wallet doesn't exist just log an error - we can't create
                    # it without an accountID
                    if wallet is None:
                        self.log_warn("No matching CorpWallet object for Corp %s Account %s", corporation.id, row.attrib['accountKey'])

                    # If the wallet exists and the description has changed, update it
                    elif wallet.description != row.attrib['description']:
                            wallet.description = row.attrib['description']
                            wallet.save()

        corporation.save()

        return True

# ---------------------------------------------------------------------------
