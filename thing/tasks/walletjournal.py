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

from decimal import Decimal

from collections import OrderedDict

from .apitask import APITask

from thing.models import Character, Corporation, JournalEntry, RefType, APIKey

# ---------------------------------------------------------------------------
# number of rows to request per WalletTransactions call, max is 2560
TRANSACTION_ROWS = 2560


class WalletJournal(APITask):
    name = 'thing.wallet_journal'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Make sure the character exists
        try:
            character = Character.objects.select_related('details').get(pk=character_id)
        except Character.DoesNotExist:
            self.log_warn('Character %s does not exist!', character_id)
            return

        # Corporation key, visit each related CorpWallet
        if self.apikey.key_type == APIKey.CORPORATION_TYPE:
            for corpwallet in self.apikey.corporation.corpwallet_set.all():
                result = self._work(url, character, corpwallet)
                if result is False:
                    return

                # _wjs_work(character, corpwallet)

        # Account/character key
        else:
            result = self._work(url, character)
            if result is False:
                return

            # _wjs_work(character)

        return True

    # Do the actual work for wallet journal entries
    def _work(self, url, character, corp_wallet=None):
        # Initialise stuff
        params = {
            'characterID': character.id,
            'rowCount': TRANSACTION_ROWS,
        }

        # Corporation key
        if self.apikey.key_type == APIKey.CORPORATION_TYPE:
            params['accountKey'] = corp_wallet.account_key
            je_filter = JournalEntry.objects.filter(corp_wallet=corp_wallet)
        # Account/Character key
        else:
            je_filter = JournalEntry.objects.filter(corp_wallet=None, character=character)

        # Loop until we run out of entries
        bulk_data = OrderedDict()
        ref_type_ids = set()
        tax_corp_ids = set()

        while True:
            if self.fetch_api(url, params) is False or self.root is None:
                return False

            refID = 0
            count = 0
            for row in self.root.findall('result/rowset/row'):
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
            j_ids = set(je_filter.filter(ref_id__in=bulk_data.keys()).values_list('ref_id', flat=True))

            # Fetch ref types
            rt_map = RefType.objects.in_bulk(ref_type_ids)

            # Fetch tax corporations
            corp_map = Corporation.objects.in_bulk(tax_corp_ids)

            new = []
            for refID, row in bulk_data.items():
                # Skip JournalEntry objects that we already have
                if refID in j_ids:
                    continue

                # RefType
                refTypeID = int(row.attrib['refTypeID'])
                ref_type = rt_map.get(refTypeID)
                if ref_type is None:
                    self.log_warn('Invalid refTypeID #%s', refTypeID)
                    continue

                # Tax receiver corporation ID - doesn't exist for /corp/ calls?
                taxReceiverID = row.attrib.get('taxReceiverID', '')
                if taxReceiverID.isdigit():
                    trid = int(taxReceiverID)
                    tax_corp = corp_map.get(trid)
                    if tax_corp is None:
                        if trid not in new_chars:
                            self.log_warn('Invalid taxReceiverID #%d', trid)
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
                    date=self.parse_api_date(row.attrib['date']),
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
                if self.apikey.key_type == APIKey.CORPORATION_TYPE:
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
