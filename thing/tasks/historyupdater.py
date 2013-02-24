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
