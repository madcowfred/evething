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

from django.contrib.auth.decorators import login_required

from thing.models import *
from thing.stuff import *

# ---------------------------------------------------------------------------
# Contracts
@login_required
def contracts(request):
    character_ids = list(Character.objects.filter(apikeys__user=request.user.id).distinct().values_list('id', flat=True))
    corporation_ids = list(APIKey.objects.filter(user=request.user).exclude(corp_character=None).values_list('corp_character__corporation__id', flat=True))

    # Whee~
    contracts = Contract.objects.select_related('issuer_char', 'issuer_corp', 'start_station', 'end_station')
    contracts = contracts.filter(
        Q(character__in=character_ids, corporation__isnull=True)
        |
        Q(corporation__in=corporation_ids)
    )

    lookup_ids = set()
    for contract in contracts:
        # Add the ids to the lookup set
        if contract.assignee_id:
            lookup_ids.add(contract.assignee_id)
        if contract.acceptor_id:
            lookup_ids.add(contract.acceptor_id)

    # Do some lookups
    char_map = Character.objects.in_bulk(lookup_ids)
    corp_map = Corporation.objects.in_bulk(lookup_ids)
    alliance_map = Alliance.objects.in_bulk(lookup_ids)

    # Now attach those to each contract
    contract_ids = set()
    contract_list = []
    for contract in contracts:
        # Skip duplicate contracts
        if contract.contract_id in contract_ids:
            continue
        contract_ids.add(contract.contract_id)
        contract_list.append(contract)

        # Assign a status icon to each contract
        if contract.status.startswith('Completed'):
            contract.z_status_icon = 'completed'
        elif contract.status == 'InProgress':
            contract.z_status_icon = 'inprogress'
        elif contract.status in ('Cancelled', 'Deleted', 'Failed', 'Rejected'):
            contract.z_status_icon = 'failed'
        elif contract.status == 'Outstanding':
            contract.z_status_icon = 'outstanding'
        else:
            contract.z_status_icon = 'unknown'

        if contract.assignee_id:
            # Assignee
            char = char_map.get(contract.assignee_id, None)
            if char is not None:
                contract.z_assignee_char = char

            corp = corp_map.get(contract.assignee_id, None)
            if corp is not None:
                contract.z_assignee_corp = corp
            
            alliance = alliance_map.get(contract.assignee_id, None)
            if alliance is not None:
                contract.z_assignee_alliance = alliance

            # Acceptor
            char = char_map.get(contract.acceptor_id, None)
            if char is not None:
                contract.z_acceptor_char = char

            corp = corp_map.get(contract.acceptor_id, None)
            if corp is not None:
                contract.z_acceptor_corp = corp

    # Render template
    return render_page(
        'thing/contracts.html',
        dict(
            characters=character_ids,
            contracts=contract_list,
            char_map=char_map,
            corp_map=corp_map,
            alliance_map=alliance_map,
        ),
        request,
        character_ids,
        corporation_ids,
    )

# ---------------------------------------------------------------------------
