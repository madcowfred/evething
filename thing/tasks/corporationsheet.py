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

from .apitask import APITask

from thing.models import CorpWallet


class CorporationSheet(APITask):
    name = 'thing.corporation_sheet'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Fetch the API data
        params = {'characterID': character_id}
        if self.fetch_api(url, params) is False or self.root is None:
            return

        corporation = self.apikey.corporation

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
