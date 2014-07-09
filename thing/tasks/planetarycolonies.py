# ------------------------------------------------------------------------------
# Copyright (c) 2010-2014, EVEthing team
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

from celery.execute import send_task

from .apitask import APITask

from thing.models import System, Character, Colony


class PlanetaryColonies(APITask):
    name = 'thing.planetary_colonies'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Make sure the character exists
        try:
            character = Character.objects.select_related('details').get(pk=character_id)
        except Character.DoesNotExist:
            self.log_warn('Character %s does not exist!', character_id)
            return

        params = {'characterID': character_id}
        if self.fetch_api(url, params) is False or self.root is None:
            return

        c_filter = Colony.objects.filter(character=character)

        c_map = {}
        for colony in c_filter:
            c_map[colony.planet_id] = colony

        system_ids = set()
        rows = []

        for row in self.root.findall('result/rowset/row'):
            rows.append(row)
            system_ids.add(int(row.attrib['solarSystemID']))

        system_map = System.objects.in_bulk(system_ids)

        for row in rows:
            planet_id = int(row.attrib['planetID'])
            colony = c_map.get(planet_id, None)
            if colony is not None:
                colony.last_update = self.parse_api_date(row.attrib['lastUpdate'])
                colony.level = int(row.attrib['upgradeLevel'])
                colony.pins = int(row.attrib['numberOfPins'])
                colony.save()
                del c_map[planet_id]
            else:
                colony = Colony()
                colony.character = character
                colony.planet_id = planet_id
                colony.system = system_map.get(int(row.attrib['solarSystemID']))
                colony.planet = row.attrib['planetName']
                colony.planet_type = row.attrib['planetTypeName']
                colony.last_update = self.parse_api_date(row.attrib['lastUpdate'])
                colony.level = int(row.attrib['upgradeLevel'])
                colony.pins = int(row.attrib['numberOfPins'])
                colony.save()

            if colony.id:
                send_task(
                    'thing.planetary_pins',
                    args=(apikey_id, character_id, colony.id),
                    kwargs={},
                    queue='et_medium',
                )

        # Remove old colonies that weren't present in the current API request
        for old_colony in c_map:
            old_colony.delete()

        return True
