import os
import sys

from .apitask import APITask

from thing.models import Alliance, Corporation

# ---------------------------------------------------------------------------

class AllianceList(APITask):
    name = 'thing.alliance_list'

    def run(self, url, taskstate_id, apikey_id, zero):
        if self.init(taskstate_id) is False:
            return

        # Fetch the API data
        if self.fetch_api(url, {}, use_auth=False) is False or self.root is None:
            return

        # Fetch existing Alliance IDs
        alliance_map = {}
        for alliance_id in Alliance.objects.values_list('id', flat=True):
            alliance_map[alliance_id] = True

        # Fetch existing Corporation objects
        corporation_map = {}
        for corporation in Corporation.objects.iterator():
            corporation_map[corporation.id] = corporation

        # Gather various data out of the monstrous XML
        alliance_data = {}
        corp_ids = []
        new = []
        for row in self.root.findall('result/rowset/row'):
            allianceID = int(row.attrib['allianceID'])
            alliance_data[allianceID] = []

            # Create a new Alliance object if it doesn't exist
            if allianceID not in alliance_map:
                alliance = Alliance(
                    id=allianceID,
                    name=row.attrib['name'],
                    short_name=row.attrib['shortName'],
                )
                new.append(alliance)
                alliance_map[allianceID] = True

            # Save Corporation IDs for later
            for corp_row in row.findall('rowset/row'):
                corporationID = int(corp_row.attrib['corporationID'])
                alliance_data[allianceID].append(corporationID)
                corp_ids.append(corporationID)

        # Bulk create any new Alliance objects
        if new:
            Alliance.objects.bulk_create(new)

        # Remove non-existent Alliance foreign keys from Corporation objects
        Corporation.objects.exclude(alliance__in=alliance_map.keys()).update(alliance=None)
        # Remove non-existent Alliance objects
        Alliance.objects.exclude(pk__in=alliance_map.keys()).delete()

        # Check all Corporations for each Alliance
        new = []
        for allianceID, corporations in alliance_data.items():
            for corpID in corporations:
                corporation = corporation_map.get(corpID)

                # Corporation does not exist, create it
                if corporation is None:
                    new.append(Corporation(
                        id=corpID,
                        name='*UNKNOWN*',
                        alliance_id=allianceID,
                    ))
                # Corporation does exist and Alliance has changed, update it
                elif corporation.alliance_id != allianceID:
                    corporation.alliance_id = allianceID
                    corporation.save()

        # Bulk create any new Corporation objects
        if new:
            Corporation.objects.bulk_create(new)

        return True

# ---------------------------------------------------------------------------
