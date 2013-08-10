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
