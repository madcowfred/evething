import os
import sys

from .apitask import APITask

# need to import model definitions from frontend
from thing.models import RefType

# ---------------------------------------------------------------------------

class RefTypes(APITask):
    name = 'thing.ref_types'

    def run(self, url, taskstate_id, apikey_id, zero):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Fetch the API data
        if self.fetch_api(url, {}, use_auth=False) is False or self.root is None:
            return

        # Build a refTypeID:row dictionary
        bulk_data = {}
        for row in self.root.findall('result/rowset/row'):
            bulk_data[int(row.attrib['refTypeID'])] = row

        # Bulk retrieve all of those stations that exist
        rt_map = RefType.objects.in_bulk(bulk_data.keys())

        new = []
        for refTypeID, row in bulk_data.items():
            reftype = rt_map.get(refTypeID)

            # RefType does not exist, make a new one
            if reftype is None:
                new.append(RefType(
                    id=refTypeID,
                    name=row.attrib['refTypeName'],
                ))

            # RefType exists and name has changed, update it
            elif reftype.name != row.attrib['refTypeName']:
                reftype.name = row.attrib['refTypeName']
                reftype.save()

        # Create any new stations
        if new:
            RefType.objects.bulk_create(new)

        return True

# ---------------------------------------------------------------------------
