import datetime
import os
import sys

from decimal import *

from django.core.urlresolvers import reverse

from .apitask import APITask

from thing.models import Character, CorpWallet, Event, Item, MarketOrder, Station

# ---------------------------------------------------------------------------

class MarketOrders(APITask):
    name = 'thing.market_orders'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return
        
        # Make sure the character exists
        try:
            character = Character.objects.select_related('details').get(pk=character_id)
        except Character.DoesNotExist:
            self.log_warn('Character %s does not exist!', character_id)
            return

        # Initialise for corporate key
        if self.apikey.corp_character:
            mo_filter = MarketOrder.objects.filter(corp_wallet__corporation=character.corporation)

            wallet_map = {}
            for cw in CorpWallet.objects.filter(corporation=character.corporation):
                wallet_map[cw.account_key] = cw

        # Initialise for other keys
        else:
            mo_filter = MarketOrder.objects.filter(corp_wallet=None, character=character)

        mo_filter = mo_filter.select_related('item')

        # Fetch the API data
        params = { 'characterID': character_id }
        if self.fetch_api(url, params) is False or self.root is None:
            return

        # Generate an order_id map
        order_map = {}
        for mo in mo_filter:
            order_map[mo.order_id] = mo
        
        # Iterate over the returned result set
        char_ids = set()
        item_ids = set()
        station_ids = set()

        rows = []
        seen = []
        for row in self.root.findall('result/rowset/row'):
            order_id = int(row.attrib['orderID'])
            
            # Order exists
            order = order_map.get(order_id)
            if order is not None:
                # Order is still active, update relevant details
                if row.attrib['orderState'] == '0':
                    issued = self.parse_api_date(row.attrib['issued'])
                    volRemaining = int(row.attrib['volRemaining'])
                    escrow = Decimal(row.attrib['escrow'])
                    price = Decimal(row.attrib['price'])

                    if issued > order.issued or volRemaining != order.volume_remaining or \
                       escrow != order.escrow or price != order.price:
                        order.issued = issued
                        order.expires = issued + datetime.timedelta(int(row.attrib['duration']))
                        order.volume_remaining = volRemaining
                        order.escrow = escrow
                        order.price = price
                        order.total_price = order.volume_remaining * order.price
                        order.save()
                    
                    seen.append(order_id)
            
            # Doesn't exist and is active, save data for later
            elif row.attrib['orderState'] == '0':
                char_ids.add(int(row.attrib['charID']))
                item_ids.add(int(row.attrib['typeID']))
                station_ids.add(int(row.attrib['stationID']))

                rows.append(row)
                seen.append(order_id)

        # Bulk query data
        char_map = Character.objects.in_bulk(char_ids)
        item_map = Item.objects.in_bulk(item_ids)
        station_map = Station.objects.in_bulk(station_ids)

        # Create new MarketOrder objects
        new = []
        for row in rows:
            item = item_map.get(int(row.attrib['typeID']))
            if item is None:
                self.log_warn("No matching Item %s", row.attrib['typeID'])
                continue

            station = station_map.get(int(row.attrib['stationID']))
            if station is None:
                self.log_warn("No matching Station %s", row.attrib['stationID'])
                continue

            # Create the new order object
            buy_order = (row.attrib['bid'] == '1')
            remaining = int(row.attrib['volRemaining'])
            price = Decimal(row.attrib['price'])
            issued = self.parse_api_date(row.attrib['issued'])

            order = MarketOrder(
                order_id=row.attrib['orderID'],
                station=station,
                item=item,
                character=character,
                escrow=Decimal(row.attrib['escrow']),
                creator_character_id=row.attrib['charID'],
                price=price,
                total_price=remaining * price,
                buy_order=buy_order,
                volume_entered=int(row.attrib['volEntered']),
                volume_remaining=remaining,
                minimum_volume=int(row.attrib['minVolume']),
                issued=issued,
                expires=issued + datetime.timedelta(int(row.attrib['duration'])),
            )
            # Set the corp_wallet for corporation API requests
            if self.apikey.corp_character:
                order.corp_wallet = wallet_map.get(int(row.attrib['accountKey']))

            new.append(order)

        # Insert any new orders
        if new:
            MarketOrder.objects.bulk_create(new)

        # Any orders we didn't see need to be deleted - issue events first
        to_delete = mo_filter.exclude(pk__in=seen)
        now = datetime.datetime.now()
        for order in to_delete.select_related():
            if order.buy_order:
                buy_sell = 'buy'
            else:
                buy_sell = 'sell'
            
            if order.corp_wallet:
                order_type = 'corporate'
            else:
                order_type = 'personal'

            url = '%s?ft=item&fc=eq&fv=%s' % (reverse('thing.views.transactions'), order.item.name)
            text = '%s: %s %s order for <a href="%s">%s</a> completed/expired (%s)' % (
                order.station.short_name,
                order_type,
                buy_sell,
                url, 
                order.item.name,
                order.character.name,
            )

            event = Event(
                user_id=self.apikey.user.id,
                issued=now,
                text=text,
            )
            event.save()

        # Then delete
        to_delete.delete()

        return True

# ---------------------------------------------------------------------------
