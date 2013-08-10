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
from thing.models import PriceHistory

# ---------------------------------------------------------------------------

HISTORY_PER_REQUEST = 50
HISTORY_URL = 'http://goonmetrics.com/api/price_history/?region_id=10000002&type_id=%s'

# ---------------------------------------------------------------------------

class HistoryUpdater(APITask):
    name = 'thing.history_updater'

    def run(self):
        if self.init() is False:
            return

        # Get a list of all item_ids
        cursor = self.get_cursor()
        cursor.execute(queries.all_item_ids)

        item_ids = [row[0] for row in cursor]

        cursor.close()

        # Collect data
        new = []
        for i in range(0, len(item_ids), 50):
            # Fetch the XML
            url = HISTORY_URL % (','.join(str(z) for z in item_ids[i:i+50]))
            data = self.fetch_url(url, {})
            if data is False:
                return

            root = self.parse_xml(data)

            # Do stuff
            for t in root.findall('price_history/type'):
                item_id = int(t.attrib['id'])

                data = {}
                for hist in t.findall('history'):
                    data[hist.attrib['date']] = hist

                # Query that shit
                for ph in PriceHistory.objects.filter(region=10000002, item=item_id, date__in=data.keys()):
                    del data[str(ph.date)]

                # Add new ones
                for date, hist in data.items():
                    new.append(PriceHistory(
                        region_id=10000002,
                        item_id=item_id,
                        date=hist.attrib['date'],
                        minimum=hist.attrib['minPrice'],
                        maximum=hist.attrib['maxPrice'],
                        average=hist.attrib['avgPrice'],
                        movement=hist.attrib['movement'],
                        orders=hist.attrib['numOrders'],
                    ))

        if new:
            PriceHistory.objects.bulk_create(new)

        return True

# ---------------------------------------------------------------------------
