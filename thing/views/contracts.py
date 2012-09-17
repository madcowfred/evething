#from django.conf import settings
from django.contrib.auth.decorators import login_required
#from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.template import RequestContext

from coffin.shortcuts import *

from thing.models import *

# ---------------------------------------------------------------------------
# Contracts
@login_required
def contracts(request):
    characters = list(Character.objects.filter(apikeys__user=request.user.id).distinct().values_list('id', flat=True))
    corporations = list(APIKey.objects.filter(user=request.user).exclude(corp_character=None).values_list('corp_character__corporation__id', flat=True))

    # Whee~
    contracts = Contract.objects.select_related('issuer_char', 'issuer_corp', 'start_station', 'end_station')
    contracts = contracts.filter(
        (
            (
                Q(issuer_char_id__in=characters) |
                Q(assignee_id__in=characters) |
                Q(acceptor_id__in=characters)
            )
            &
            Q(for_corp=False)
        )
        |
        (
            (
                Q(issuer_corp_id__in=corporations) |
                Q(assignee_id__in=corporations) |
                Q(acceptor_id__in=corporations)
            )
            &
            Q(for_corp=True)
        )
    )

    lookup_ids = set()
    for contract in contracts:
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

        # Add the ids to the lookup set
        if contract.assignee_id:
            lookup_ids.add(contract.assignee_id)
        if contract.acceptor_id:
            lookup_ids.add(contract.acceptor_id)

    # Do some lookups
    char_map = SimpleCharacter.objects.in_bulk(lookup_ids)
    corp_map = Corporation.objects.in_bulk(lookup_ids)
    alliance_map = Alliance.objects.in_bulk(lookup_ids)

    # Now attach those to each contract
    for contract in contracts:
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


    return render_to_response(
        'thing/contracts.html',
        dict(
            characters=characters,
            contracts=contracts,
            char_map=char_map,
            corp_map=corp_map,
            alliance_map=alliance_map,
        ),
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
