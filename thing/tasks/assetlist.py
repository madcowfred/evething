import datetime

from decimal import *

from .apitask import APITask

from thing import queries
from thing.models import Asset, Character, InventoryFlag, Item, Station, System

# ---------------------------------------------------------------------------

class AssetList(APITask):
    name = 'thing.asset_list'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return
        
        # Make sure the character exists
        try:
            character = Character.objects.select_related('details').get(pk=character_id)
        except Character.DoesNotExist:
            self.log_warn('Character %s does not exist!', character_id)
            return

        # Initialise for corporate query
        if self.apikey.corp_character:
            a_filter = Asset.objects.filter(character=character, corporation_id=self.apikey.corp_character.corporation.id)
        # Initialise for character query
        else:
            a_filter = Asset.objects.filter(character=character, corporation_id__isnull=True)

        # Fetch the API data
        params = { 'characterID': character.id }
        if self.fetch_api(url, params) is False or self.root is None:
            return

        # ACTIVATE RECURSION :siren:
        data = {
            'assets': [],
            'locations': set(),
            'items': set(),
            'flags': set(),
        }
        self._find_assets(data, self.root.find('result/rowset'))

        # Bulk query data
        item_map = Item.objects.in_bulk(data['items'])
        station_map = Station.objects.in_bulk(data['locations'])
        system_map = System.objects.in_bulk(data['locations'])
        flag_map = InventoryFlag.objects.in_bulk(data['flags'])

        # Build new Asset objects for each row
        assets = []
        for asset_id, location_id, parent_id, item_id, flag_id, quantity, rawQuantity, singleton in data['assets']:
            item = item_map.get(item_id)
            if item is None:
                self.log_warn('Invalid item_id %s', item_id)
                continue

            inv_flag = flag_map.get(flag_id)
            if inv_flag is None:
                self.log_warn('Invalid flag_id %s', flag_id)
                continue

            asset = Asset(
                asset_id=asset_id,
                parent=parent_id,
                character=character,
                system=system_map.get(location_id),
                station=station_map.get(location_id),
                item=item,
                inv_flag=inv_flag,
                quantity=quantity,
                raw_quantity=rawQuantity,
                singleton=singleton,
            )
            if self.apikey.corp_character:
                asset.corporation = self.apikey.corp_character.corporation

            assets.append(asset)

        # Delete existing assets, it's way too painful trying to deal with changes
        cursor = self.get_cursor()
        if self.apikey.corp_character:
            cursor.execute(queries.asset_delete_corp, [self.apikey.corp_character.corporation.id])
        else:
            cursor.execute(queries.asset_delete_char, [character_id])
        cursor.close()

        # Bulk insert new assets
        Asset.objects.bulk_create(assets)


        # Fetch names (via Locations API) for assets
        # if self.apikey.corp_character is None and APIKey.CHAR_LOCATIONS_MASK in self.apikey.get_masks():
        #     a_filter = a_filter.filter(singleton=True, item__item_group__category__name__in=('Celestial', 'Ship'))

        #     # Get ID list
        #     ids = map(str, a_filter.values_list('asset_id', flat=True))
        #     if ids:
        #         # Fetch the API data
        #         params['IDs'] = ','.join(map(str, ids))
        #         if self.fetch_api(LOCATIONS_URL, params) is False or self.root is None:
        #             self.completed()
        #             return

        #         # Build a map of assetID:assetName
        #         bulk_data = {}
        #         for row in self.root.findall('result/rowset/row'):
        #             bulk_data[int(row.attrib['itemID'])] = row.attrib['itemName']

        #         # Bulk query them
        #         for asset in a_filter.filter(asset_id__in=bulk_data.keys()):
        #             asset_name = bulk_data.get(asset.asset_id)
        #             if asset.name is None or asset.name != asset_name:
        #                 asset.name = asset_name
        #                 asset.save()

        return True


    # Recursively visit the assets tree and gather data
    def _find_assets(self, data, rowset, location_id=0, parent_id=0):
        for row in rowset.findall('row'):
            # No container_id (parent)
            if location_id == 0:
                #if 'locationID' in row.attrib:
                location_id = int(row.attrib['locationID'])

                # :ccp: as fuck
                # http://wiki.eve-id.net/APIv2_Corp_AssetList_XML#officeID_to_stationID_conversion
                if 66000000 <= location_id <= 66014933:
                    location_id -= 6000001
                elif 66014934 <= location_id <= 67999999:
                    location_id -= 6000000

                data['locations'].add(location_id)

            #else:
            #    location_id = None

            asset_id = int(row.attrib['itemID'])

            item_id = int(row.attrib['typeID'])
            data['items'].add(item_id)

            flag_id = int(row.attrib['flag'])
            data['flags'].add(flag_id)

            data['assets'].append([
                asset_id,
                location_id,
                parent_id,
                item_id,
                flag_id,
                int(row.attrib.get('quantity', '0')),
                int(row.attrib.get('rawQuantity', '0')),
                int(row.attrib.get('singleton', '0')),
            ])

            # Now we need to recurse into children rowsets
            for rowset in row.findall('rowset'):
                self._find_assets(data, rowset, location_id, asset_id)

# ---------------------------------------------------------------------------
