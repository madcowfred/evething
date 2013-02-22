import os
import sys

from .apitask import APITask

# need to import model definitions from frontend
from thing.models import Station

# ---------------------------------------------------------------------------

class ConquerableStationList(APITask):
    name = 'thing.conquerable_station_list'

    def run(self, url, taskstate_id, apikey_id, zero):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Fetch the API data
        if self.fetch_api(url, {}, use_auth=False) is False or self.root is None:
            self.failed()
            return

        # Build a stationID:row dictionary
        bulk_data = {}
        for row in self.root.findall('result/rowset/row'):
            bulk_data[int(row.attrib['stationID'])] = row

        # Bulk retrieve all of those stations that exist
        station_map = Station.objects.in_bulk(bulk_data.keys())

        new = []
        for id, row in bulk_data.items():
            # If the station already exists...
            station = station_map.get(id)

            # Station does not exist, make a new one
            if station is None:
                s = Station(
                    id=id,
                    name=row.attrib['stationName'],
                    system_id=row.attrib['solarSystemID'],
                )
                s._make_shorter_name()
                new.append(s)

            # Station exists and name has changed, update it
            elif station.name != row.attrib['stationName']:
                station.name = row.attrib['stationName']
                station.save()

        # Create any new stations
        if new:
            Station.objects.bulk_create(new)

        # Job completed
        self.completed()

# ---------------------------------------------------------------------------
