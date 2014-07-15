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

from thing.models.planetarycolony import Colony
from thing.models.planetarypin import Pin, PinContent
from thing.models.item import Item


class PlanetaryPins(APITask):
    name = 'thing.planetary_pins'
    url = '/char/PlanetaryPins.xml.aspx'

    def run(self, apikey_id, character_id, colony_id):
        if self.init(apikey_id=apikey_id) is False:
            return

        try:
            colony = Colony.objects.get(id=colony_id)
        except Colony.DoesNotExist:
            self.log_warn('Colony %s does not exist!', colony_id)
            return

        params = dict(
            characterID=colony.character_id,
            planetID=colony.planet_id,
        )

        p_filter = Pin.objects.filter(colony=colony)

        p_map = {}
        old_pins = {}
        for pin in p_filter.all():
            p_map[pin.pin_id] = pin
            old_pins[pin.pin_id] = pin

        if self.fetch_api(PlanetaryPins.url, params) is False or self.root is None:
            return

        c_map = {}
        i_map = {}

        for row in self.root.findall('result/rowset/row'):
            pin_id = int(row.attrib['pinID'])

            pin = p_map.get(pin_id, None)
            if pin is None:
                pin = Pin()
                pin.pin_id = pin_id
            else:
                del old_pins[pin_id]

            pin.colony = colony
            pin.type_id = int(row.attrib['typeID'])
            pin.schematic = int(row.attrib['schematicID'])

            pin.cycle_time = int(row.attrib['cycleTime'])
            pin.quantity_per_cycle = int(row.attrib['quantityPerCycle'])

            pin.installed = self.parse_api_date(row.attrib['installTime'])
            pin.expires = self.parse_api_date(row.attrib['expiryTime'])
            pin.last_launched = self.parse_api_date(row.attrib['lastLaunchTime'])

            content_id = int(row.attrib['contentTypeID'])
            if content_id != 0:
                content = c_map.get(pin_id, [])
                content.append([content_id, int(row.attrib['contentQuantity'])])
                c_map[pin_id] = content
                item = i_map.get(content_id, None)
                if item is None:
                    i_map[content_id] = Item.objects.get(id=content_id)

            p_map[pin_id] = pin

        for pid, pin in p_map.items():
            pin.save()
            pin.pincontent_set.all().delete()
            contents = c_map.get(pid, None)
            volume = 0
            if contents is not None:
                for item, quantity in contents:
                    content = PinContent(pin=pin, item_id=item, quantity=quantity)
                    i = i_map.get(item)
                    volume += i.volume * quantity
                    content.save()
            pin.content_size = volume
            pin.save(update_fields=['content_size'])

        # Delete pins that weren't in the API results
        for pin in p_map.itervalues():
            pin.delete()

        return True
