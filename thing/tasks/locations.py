from urlparse import urljoin

from django.conf import settings
from django.core.cache import cache

from .apitask import APITask
from thing.models import Asset

# ---------------------------------------------------------------------------

class Locations(APITask):
    name = 'thing.locations'
    url = urljoin(settings.API_HOST, '/char/Locations.xml.aspx')

    def run(self, apikey_id, character_id, asset_id):
        if self.init(apikey_id=apikey_id) is False:
            return

        # Fetch the API data
        params = {
            'characterID': str(character_id),
            'IDs': str(asset_id),
        }
        if self.fetch_api(self.url, params) is False or self.root is None:
            return

        # Find and update the asset
        for row in self.root.findall('result/rowset/row'):
            try:
                asset = Asset.objects.get(character=character_id, corporation_id=0, asset_id=asset_id)
            except Asset.DoesNotExist:
                return

            if asset.name != row.attrib['itemName']:
                asset.name = row.attrib['itemName']
                asset.save(update_fields=['name'])

        return True

# ---------------------------------------------------------------------------
