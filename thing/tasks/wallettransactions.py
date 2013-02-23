from decimal import *

from .apitask import APITask

from thing.models import Character, Corporation, CorpWallet, Item, Station, Transaction

# ---------------------------------------------------------------------------
# number of rows to request per WalletTransactions call, max is 2560
TRANSACTION_ROWS = 2560

class WalletTransactions(APITask):
    name = 'thing.wallet_transactions'

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
        if self.apikey.corp_character:
            for corpwallet in self.apikey.corp_character.corporation.corpwallet_set.all():
                result = self._work(url, character, corpwallet)
                if result is False:
                    return

        # Account/character key
        else:
            result = self._work(url, character)
            if result is False:
                return

        return True

    # Do the actual work for wallet transactions
    def _work(self, url, character, corp_wallet=None):
        # Initialise stuff
        params = {
            'characterID': character.id,
            'rowCount': TRANSACTION_ROWS,
        }
        
        # Corporation key
        if self.apikey.corp_character:
            params['accountKey'] = corp_wallet.account_key
            t_filter = Transaction.objects.filter(corp_wallet=corp_wallet)
        # Account/Character key
        else:
            t_filter = Transaction.objects.filter(corp_wallet=None, character=character)

        # Stuff to collect
        bulk_data = {}
        char_ids = set()
        item_ids = set()
        station_ids = set()

        # Loop until we run out of transactions
        while True:
            if self.fetch_api(url, params) is False or self.root is None:
                return False
            
            rows = self.root.findall('result/rowset/row')
            # empty result set = no transactions ever on this wallet
            if not rows:
                break
            
            # Gather bulk data
            for row in rows:
                transaction_id = int(row.attrib['transactionID'])
                bulk_data[transaction_id] = row

                char_ids.add(int(row.attrib['clientID']))
                item_ids.add(int(row.attrib['typeID']))
                station_ids.add(int(row.attrib['stationID']))

                if self.apikey.corp_character:
                    char_ids.add(int(row.attrib['characterID']))

            # If we got MAX rows we should retrieve some more
            if len(rows) == TRANSACTION_ROWS:
                params['beforeTransID'] = transaction_id
            else:
                break

        # Retrieve any existing transactions
        t_ids = set(t_filter.filter(transaction_id__in=bulk_data.keys()).values_list('transaction_id', flat=True))

        # Fetch bulk data
        char_map = Character.objects.in_bulk(char_ids)
        corp_map = Corporation.objects.in_bulk(char_ids.difference(char_map))
        item_map = Item.objects.in_bulk(item_ids)
        station_map = Station.objects.in_bulk(station_ids)
        
        # Iterate over scary data
        new = []
        for transaction_id, row in bulk_data.items():
            transaction_time = self.parse_api_date(row.attrib['transactionDateTime'])
            
            # Skip corporate transactions if this is a personal call, we have no idea
            # what CorpWallet this transaction is related to otherwise :ccp:
            if row.attrib['transactionFor'].lower() == 'corporation' and not self.apikey.corp_character:
                continue

            # Handle possible new clients
            client_id = int(row.attrib['clientID'])
            client = char_map.get(client_id, corp_map.get(client_id, None))
            if client is None:
                try:
                    client = Character.objects.create(
                        id=client_id,
                        name=row.attrib['clientName'],
                    )
                except IntegrityError:
                    client = Character.objects.get(id=client_id)

                char_map[client_id] = client

            # Check to see if this transaction already exists
            if transaction_id not in t_ids:
                # Make sure the item is valid
                item = item_map.get(int(row.attrib['typeID']))
                if item is None:
                    self.log_warn('Invalid item_id %s', row.attrib['typeID'])
                    continue

                # Make sure the station is valid
                station = station_map.get(int(row.attrib['stationID']))
                if station is None:
                    self.log_warn('Invalid station_id %s', row.attrib['stationID'])
                    continue
                
                # For a corporation key, make sure the character exists
                if self.apikey.corp_character:
                    char_id = int(row.attrib['characterID'])
                    char = char_map.get(char_id, None)
                    # Doesn't exist, create it
                    if char is None:
                        char = Character.objects.create(
                            id=char_id,
                            name=row.attrib['characterName'],
                            corporation=self.apikey.corp_character.corporation,
                        )
                        char_map[char_id] = char
                # Any other key = just use the supplied character
                else:
                    char = character
                
                # Create a new transaction object and save it
                quantity = int(row.attrib['quantity'])
                price = Decimal(row.attrib['price'])
                buy_transaction = (row.attrib['transactionType'] == 'buy')

                t = Transaction(
                    station=station,
                    item=item,
                    character=char,
                    transaction_id=transaction_id,
                    date=transaction_time,
                    buy_transaction=buy_transaction,
                    quantity=quantity,
                    price=price,
                    total_price=quantity * price,
                )
                
                # Set the corp_character for corporation API requests
                if self.apikey.corp_character:
                    t.corp_wallet = corp_wallet
                
                # Set whichever client type is relevant
                if isinstance(client, Character):
                    t.other_char_id = client.id
                else:
                    t.other_corp_id = client.id
                
                new.append(t)

        # Create any new transaction objects
        if new:
            Transaction.objects.bulk_create(new)

        return True

# ---------------------------------------------------------------------------
