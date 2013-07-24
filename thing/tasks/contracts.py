import datetime

from decimal import *

from .apitask import APITask

from thing.models import Alliance, Character, Contract, ContractItem, Corporation, Event, Station

# ---------------------------------------------------------------------------

class Contracts(APITask):
    name = 'thing.contracts'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return
        
        # Make sure the character exists
        try:
            character = Character.objects.select_related('details').get(pk=character_id)
        except Character.DoesNotExist:
            self.log_warn('Character %s does not exist!', character_id)
            return
        
        now = datetime.datetime.now()

        # Initialise for corporate query
        if self.apikey.corp_character:
            c_filter = Contract.objects.filter(corporation=self.apikey.corp_character.corporation)
        
        # Initialise for character query
        else:
            c_filter = Contract.objects.filter(character=character, corporation__isnull=True)

        params = { 'characterID': character_id }
        if self.fetch_api(url, params) is False or self.root is None:
            return


        # Retrieve a list of this user's characters and corporations
        #user_chars = list(Character.objects.filter(apikeys__user=self.apikey.user).values_list('id', flat=True))
        #user_corps = list(APIKey.objects.filter(user=self.apikey.user).exclude(corp_character=None).values_list('corp_character__corporation__id', flat=True))


        # First we need to get all of the acceptor and assignee IDs
        contract_ids = set()
        station_ids = set()
        lookup_ids = set()
        lookup_corp_ids = set()
        contract_rows = []
        # <row contractID="58108507" issuerID="2004011913" issuerCorpID="751993277" assigneeID="401273477"
        #      acceptorID="0" startStationID="60014917" endStationID="60003760" type="Courier" status="Outstanding"
        #      title="" forCorp="0" availability="Private" dateIssued="2012-08-02 06:50:29" dateExpired="2012-08-09 06:50:29"
        #      dateAccepted="" numDays="7" dateCompleted="" price="0.00" reward="3000000.00" collateral="0.00" buyout="0.00"
        #      volume="10000"/>
        for row in self.root.findall('result/rowset/row'):
            if self.apikey.corp_character:
                # corp keys don't care about non-corp orders
                if row.attrib['forCorp'] == '0':
                    continue
                # corp keys don't care about orders they didn't issue - another fun
                # bug where corp keys see alliance contracts they didn't make  :ccp:
                if self.apikey.corp_character.corporation.id not in (int(row.attrib['issuerCorpID']),
                    int(row.attrib['assigneeID']), int(row.attrib['acceptorID'])):
                    #logger.info('Skipping non-corp contract :ccp:')
                    continue

            # non-corp keys don't care about corp orders
            if not self.apikey.corp_character and row.attrib['forCorp'] == '1':
                continue

            contract_ids.add(int(row.attrib['contractID']))
            
            station_ids.add(int(row.attrib['startStationID']))
            station_ids.add(int(row.attrib['endStationID']))

            lookup_ids.add(int(row.attrib['issuerID']))
            lookup_corp_ids.add(int(row.attrib['issuerCorpID']))

            if row.attrib['assigneeID'] != '0':
                lookup_ids.add(int(row.attrib['assigneeID']))
            if row.attrib['acceptorID'] != '0':
                lookup_ids.add(int(row.attrib['acceptorID']))
            
            contract_rows.append(row)

        # Fetch bulk data
        char_map = Character.objects.in_bulk(lookup_ids)
        corp_map = Corporation.objects.in_bulk(lookup_ids | lookup_corp_ids)
        alliance_map = Alliance.objects.in_bulk(lookup_ids)
        station_map = Station.objects.in_bulk(station_ids)
        
        # Add missing IDs as *UNKNOWN* Characters for now
        new = []
        for new_id in lookup_ids.difference(char_map, corp_map, alliance_map, lookup_corp_ids):
            char = Character(
                id=new_id,
                name="*UNKNOWN*",
            )
            new.append(char)
            char_map[new_id] = char

        if new:
            Character.objects.bulk_create(new)

        # Add missing Corporations too
        new = []
        for new_id in lookup_corp_ids.difference(corp_map):
            corp = Corporation(
                id=new_id,
                name="*UNKNOWN*",
            )
            new.append(corp)
            corp_map[new_id] = corp

        if new:
            Corporation.objects.bulk_create(new)

        # Fetch station data

        # Fetch all existing contracts
        c_map = {}
        for contract in c_filter.filter(contract_id__in=contract_ids):
            c_map[contract.contract_id] = contract


        # Finally, after all of that other bullshit, we can actually deal with
        # our goddamn contract rows
        new_contracts = []
        new_events = []

        # <row contractID="58108507" issuerID="2004011913" issuerCorpID="751993277" assigneeID="401273477"
        #      acceptorID="0" startStationID="60014917" endStationID="60003760" type="Courier" status="Outstanding"
        #      title="" forCorp="0" availability="Private" dateIssued="2012-08-02 06:50:29" dateExpired="2012-08-09 06:50:29"
        #      dateAccepted="" numDays="7" dateCompleted="" price="0.00" reward="3000000.00" collateral="0.00" buyout="0.00"
        #      volume="10000"/>
        for row in contract_rows:
            contractID = int(row.attrib['contractID'])
            
            issuer_char = char_map.get(int(row.attrib['issuerID']))
            if issuer_char is None:
                self.log_warn('Invalid issuerID %s', row.attrib['issuerID'])
                continue

            issuer_corp = corp_map.get(int(row.attrib['issuerCorpID']))
            if issuer_corp is None:
                self.log_warn('Invalid issuerCorpID %s', row.attrib['issuerCorpID'])
                continue
            
            start_station = station_map.get(int(row.attrib['startStationID']))
            if start_station is None:
                self.log_warn('Invalid startStationID %s', row.attrib['startStationID'])
                continue

            end_station = station_map.get(int(row.attrib['endStationID']))
            if end_station is None:
                self.log_warn('Invalid endStationID %s', row.attrib['endStationID'])
                continue

            assigneeID = int(row.attrib['assigneeID'])
            acceptorID = int(row.attrib['acceptorID'])

            dateIssued = self.parse_api_date(row.attrib['dateIssued'])
            dateExpired = self.parse_api_date(row.attrib['dateExpired'])
            
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

            type = row.attrib['type']
            if type == 'ItemExchange':
                type = 'Item Exchange'

            contract = c_map.get(contractID, None)
            # Contract exists, maybe update stuff
            if contract is not None:
                if contract.status != row.attrib['status']:
                    text = "Contract %s changed status from '%s' to '%s'" % (
                        contract, contract.status, row.attrib['status'])
                    
                    new_events.append(Event(
                        user_id=self.apikey.user.id,
                        issued=now,
                        text=text,
                    ))

                    contract.status = row.attrib['status']
                    contract.date_accepted = dateAccepted
                    contract.date_completed = dateCompleted
                    contract.acceptor_id = acceptorID
                    contract.save()

            # Contract does not exist, make a new one
            else:
                contract = Contract(
                    character=character,
                    contract_id=contractID,
                    issuer_char=issuer_char,
                    issuer_corp=issuer_corp,
                    assignee_id=assigneeID,
                    acceptor_id=acceptorID,
                    start_station=station_map[int(row.attrib['startStationID'])],
                    end_station=station_map[int(row.attrib['endStationID'])],
                    type=type,
                    status=row.attrib['status'],
                    title=row.attrib['title'],
                    for_corp=(row.attrib['forCorp'] == '1'),
                    public=(row.attrib['availability'].lower() == 'public'),
                    date_issued=dateIssued,
                    date_expired=dateExpired,
                    date_accepted=dateAccepted,
                    date_completed=dateCompleted,
                    num_days=int(row.attrib['numDays']),
                    price=Decimal(row.attrib['price']),
                    reward=Decimal(row.attrib['reward']),
                    collateral=Decimal(row.attrib['collateral']),
                    buyout=Decimal(row.attrib['buyout']),
                    volume=Decimal(row.attrib['volume']),
                )
                if self.apikey.corp_character:
                    contract.corporation = self.apikey.corp_character.corporation

                new_contracts.append(contract)

                # If this contract is a new contract in a non-completed state, log an event
                if contract.status in ('Outstanding', 'InProgress'):
                    #if assigneeID in user_chars or assigneeID in user_corps:
                    assignee = char_map.get(assigneeID, corp_map.get(assigneeID, alliance_map.get(assigneeID)))
                    if assignee is not None:
                        text = "Contract %s was created from '%s' to '%s' with status '%s'" % (
                            contract, contract.get_issuer_name(), assignee.name, contract.status)
                        
                        new_events.append(Event(
                            user_id=self.apikey.user.id,
                            issued=now,
                            text=text,
                        ))

        # And save the damn things
        Contract.objects.bulk_create(new_contracts)
        Event.objects.bulk_create(new_events)


        # Force the queryset to update
        c_filter.update()

        # Now go fetch items for each contract
        items_url = url.replace('Contracts', 'ContractItems')
        new = []
        # Apparently courier contracts don't have ContractItems support? :ccp:
        for contract in c_filter.filter(retrieved_items=False).exclude(type='Courier'):
            params['contractID'] = contract.contract_id
            if self.fetch_api(items_url, params) is False or self.root is None:
                return

            for row in self.root.findall('result/rowset/row'):
                new.append(ContractItem(
                    contract_id=contract.contract_id,
                    item_id=row.attrib['typeID'],
                    quantity=row.attrib['quantity'],
                    raw_quantity=row.attrib.get('rawQuantity', 0),
                    singleton=row.attrib['singleton'] == '1',
                    included=row.attrib['included'] == '1',
                ))

        if new:
            ContractItem.objects.bulk_create(new)
            c_filter.update(retrieved_items=True)


        return True

# ---------------------------------------------------------------------------
