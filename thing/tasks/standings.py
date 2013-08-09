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

from decimal import *

from .apitask import APITask

from thing.models import Character, CorporationStanding, Faction, FactionStanding

# ---------------------------------------------------------------------------

class Standings(APITask):
    name = 'thing.standings'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return

        try:
            character = Character.objects.select_related('details').get(pk=character_id)
        except Character.DoesNotExist:
            self.log_warn('Character %s does not exist!', character_id)
            return

        # Fetch the API data
        params = { 'characterID': character_id }
        if self.fetch_api(url, params) is False or self.root is None:
            return

        # Build data maps
        cs_map = {}
        for cs in CorporationStanding.objects.filter(character=character):
            cs_map[cs.corporation_id] = cs

        fs_map = {}
        for fs in FactionStanding.objects.filter(character=character):
            fs_map[fs.faction_id] = fs

        # Iterate over rowsets
        for rowset in self.root.findall('result/characterNPCStandings/rowset'):
            name = rowset.attrib['name']

            # NYI: Agents
            if name == 'agents':
                continue

            # Corporations
            elif name == 'NPCCorporations':
                new = []
                for row in rowset.findall('row'):
                    id = int(row.attrib['fromID'])
                    standing = Decimal(row.attrib['standing'])

                    cs = cs_map.get(id, None)
                    # Standing doesn't exist, make a new one
                    if cs is None:
                        cs = CorporationStanding(
                            character_id=character.id,
                            corporation_id=id,
                            standing=standing,
                        )
                        new.append(cs)
                    # Exists, check for standings change
                    elif cs.standing != standing:
                        cs.standing = standing
                        cs.save()

                if new:
                    CorporationStanding.objects.bulk_create(new)

            # Factions
            elif name == 'factions':
                factions = {}
                for row in rowset.findall('row'):
                    id = int(row.attrib['fromID'])
                    standing = Decimal(row.attrib['standing'])

                    fs = fs_map.get(id, None)
                    # Standing doesn't exist, make a new one
                    if fs is None:
                        factions[id] = (row.attrib['fromName'], standing)
                    # Exists, check for standings change
                    elif fs.standing != standing:
                        fs.standing = standing
                        fs.save()

                if factions:
                    faction_ids = set(Faction.objects.filter(pk__in=factions.keys()).values_list('id', flat=True))

                    new_f = []
                    new_fs = []
                    for id, (name, standing) in factions.items():
                        if id not in faction_ids:
                            new_f.append(Faction(
                                id=id,
                                name=name,
                            ))

                        new_fs.append(FactionStanding(
                            character_id=character.id,
                            faction_id=id,
                            standing=standing,
                        ))

                    if new_f:
                        Faction.objects.bulk_create(new_f)
                    if new_fs:
                        FactionStanding.objects.bulk_create(new_fs)

        return True

# ---------------------------------------------------------------------------
