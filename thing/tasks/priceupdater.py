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

from thing import queries
from thing.models import Blueprint, BlueprintInstance, Item

# ---------------------------------------------------------------------------

CAPITAL_SHIP_GROUPS = (
    'Capital Industrial Ship',
    'Carrier',
    'Dreadnought',
    'Supercarrier',
    'Titan',
)
PRICE_PER_REQUEST = 100
PRICE_URL = 'http://goonmetrics.com/api/price_data/?station_id=60003760&type_id=%s'

# ---------------------------------------------------------------------------

class PriceUpdater(APITask):
    name = 'thing.price_updater'

    def run(self):
        if self.init() is False:
            return

        # Get a list of all item_ids
        cursor = self.get_cursor()
        cursor.execute(queries.all_item_ids)

        item_ids = [row[0] for row in cursor]

        cursor.close()

        # Bulk retrieve items
        item_map = Item.objects.in_bulk(item_ids)

        for i in range(0, len(item_ids), PRICE_PER_REQUEST):
            # Retrieve market data and parse the XML
            url = PRICE_URL % (','.join(str(item_id) for item_id in item_ids[i:i+PRICE_PER_REQUEST]))
            data = self.fetch_url(url, {})
            if data is False:
                return

            root = self.parse_xml(data)

            # Update item prices
            for t in root.findall('price_data/type'):
                item = item_map[int(t.attrib['id'])]
                item.buy_price = t.find('buy/max').text
                item.sell_price = t.find('sell/min').text
                item.save()

        # Calculate capital ship costs now
        for bp in Blueprint.objects.select_related('item').filter(item__item_group__name__in=CAPITAL_SHIP_GROUPS):
            bpi = BlueprintInstance(
                user=None,
                blueprint=bp,
                original=True,
                material_level=2,
                productivity_level=0,
            )
            bp.item.sell_price = bpi.calc_capital_production_cost()
            bp.item.save()

        return True

# ---------------------------------------------------------------------------
