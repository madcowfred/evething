# ------------------------------------------------------------------------------
# Copyright (c) 2010-2014, EVEthing team
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

from datetime import datetime, timedelta

from django.db.models import Q

from .apitask import APITask

from thing.models import Contract, Event

# Peroidic task to fix contracts that fell off the main contracts list
CONTRACT_URL = '/char/Contracts.xml.aspx'


class FixContracts(APITask):
    name = 'thing.fix_contracts'

    def run(self):
        self.init()

        lookup = {}
        new_events = []
        now = datetime.now()
        hours_ago = now - timedelta(hours=6)

        # We use hours_ago just so we try not to duplicate the chance that this call overlaps with the
        # normal Contracts APITask
        expired_contracts = Contract.objects.filter(date_expired__lte=hours_ago).filter(
            Q(status='Outstanding') | Q(status='Accepted')).prefetch_related('character__apikeys')

        # Group contracts to lookup by APIKey and Character
        for contract in expired_contracts:
            apikey = None
            for key in contract.character.apikeys.all():
                if (key.access_mask & key.CHAR_CONTRACTS_MASK) != 0:
                    apikey = key

            if apikey is None:
                self.log_error('Could not find APIKey with proper access for contract %d' % contract.id)
                return False

            if apikey.keyid not in lookup:
                lookup[apikey.keyid] = {
                    'key': apikey,
                    'contracts': []
                }

            lookup[apikey.keyid]['contracts'].append(contract)

        # Actually do the lookups
        for apikey, info in lookup.items():
            params = {
                'keyID': info['key'].keyid,
                'vCode': info['key'].vcode,
            }

            for contract in lookup[apikey]['contracts']:
                params['contractID'] = contract.contract_id
                params['characterID'] = contract.character_id

                print(params)

                """
                if self.fetch_api(CONTRACT_URL, params, use_auth=False) is False or self.root is None:
                    self.log_error(
                        'Error fetching information about contract %d using characterID %d apikey %s and vcode %s' %
                        (contract.contract_id, params['characterID'], params['keyID'], params['vCode'])
                    )
                    return False

                for row in self.root.findall('result/rowset/row'):
                    # Only care about the stuff we need to update
                    contractID = int(row.attrib['contractID'])

                    acceptorID = int(row.attrib['acceptorID'])

                    dateAccepted = row.attrib['dateAccepted']
                    if dateAccepted:
                        dateAccepted = self.parse_api_date(dateAccepted)
                    else:
                        dateAccepted = None

                    dateCompleted = row.attrib['dateCompleted']
                    if dateCompleted:
                        dateCompleted = self.parse_api_date(dateCompleted)
                    else:
                        dateCompleted = None

                    if contractID == contract.contract_id:
                        if contract.status != row.attrib['status']:
                            text = "Contract %s changed status from '%s' to '%s'" % (
                                contract.contract_id, contract.status, row.attrib['status']
                            )
                            print(text)
                            new_events.append(Event(
                                user_id=info['key'].user.id,
                                issued=now,
                                text=text,
                            ))

                            contract.status = row.attrib['status']
                            contract.date_accepted = dateAccepted
                            contract.date_completed = dateCompleted
                            contract.acceptor_id = acceptorID
                            contract.save()
                    else:
                        self.log_error('Contract %d is somehow different from requested :ccp:' % contractID)
                        return False
                """

        Event.objects.bulk_create(new_events)

        return True
