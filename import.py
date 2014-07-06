#!/usr/bin/env python
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

import os
import sys
import time

from decimal import Decimal

# Set up our environment and import settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'evething.settings'
from django.db import connections

from thing.models import *  # NOPEP8

# ---------------------------------------------------------------------------
# Override volume for ships, assembled volume is mostly useless :ccp:
PACKAGED = {
    25: 2500,    # frigate
    26: 10000,   # cruiser
    27: 50000,   # battleship
    28: 20000,   # industrial
    31: 500,     # shuttle
    324: 2500,   # assault ship
    358: 10000,  # heavy assault ship
    380: 20000,  # transport ship
    419: 15000,  # battlecruiser
    420: 5000,   # destroyer
    463: 3750,   # mining barge
    540: 15000,  # command ship
    541: 5000,   # interdictor
    543: 3750,   # exhumer
    830: 2500,   # covert ops
    831: 2500,   # interceptor
    832: 10000,  # logistics
    833: 10000,  # force recon
    834: 2500,   # stealth bomber
    893: 2500,   # electronic attack ship
    894: 10000,  # heavy interdictor
    898: 50000,  # black ops
    900: 50000,  # marauder
    906: 10000,  # combat recon
    963: 5000,   # strategic cruiser
}

# ---------------------------------------------------------------------------
# Skill map things
PREREQ_SKILLS = {
    182: 0,
    183: 1,
    184: 2,
    1285: 3,
    1289: 4,
    1290: 5,
}
PREREQ_LEVELS = {
    277: 0,
    278: 1,
    279: 2,
    1286: 3,
    1287: 4,
    1288: 5,
}


def time_func(text, f):
    start = time.time()
    print '=> %s:' % text,
    sys.stdout.flush()

    added = f()

    print '%d (%0.2fs)' % (added, time.time() - start)


class Importer:
    def __init__(self):
        self.cursor = connections['import'].cursor()
        # sqlite3 UTF drama workaround
        connections['import'].connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")

    def import_all(self):
        time_func('Region', self.import_region)
        time_func('Constellation', self.import_constellation)
        time_func('System', self.import_system)
        time_func('Station', self.import_station)
        time_func('MarketGroup', self.import_marketgroup)
        time_func('ItemCategory', self.import_itemcategory)
        time_func('ItemGroup', self.import_itemgroup)
        time_func('Item', self.import_item)
        time_func('Blueprint', self.import_blueprint)
        time_func('Skill', self.import_skill)
        time_func('InventoryFlag', self.import_inventoryflag)
        time_func('NPCFaction', self.import_npcfaction)
        time_func('NPCCorporation', self.import_npccorporation)
        time_func('Item Prerequisite', self.import_item_prerequisite)

    # -----------------------------------------------------------------------
    # Regions
    def import_region(self):
        added = 0

        self.cursor.execute("SELECT regionID, regionName FROM mapRegions WHERE regionName != 'Unknown'")
        bulk_data = {}
        for row in self.cursor:
            bulk_data[int(row[0])] = row[1:]

        data_map = Region.objects.in_bulk(bulk_data.keys())

        new = []
        for id, data in bulk_data.items():
            if id in data_map:
                continue

            region = Region(
                id=id,
                name=data[0],
            )
            new.append(region)
            added += 1

        if new:
            Region.objects.bulk_create(new)

        return added

    # -----------------------------------------------------------------------
    # Constellations
    def import_constellation(self):
        added = 0

        self.cursor.execute('SELECT constellationID,constellationName,regionID FROM mapConstellations')
        bulk_data = {}
        for row in self.cursor:
            id = int(row[0])
            if id:
                bulk_data[id] = row[1:]

        data_map = Constellation.objects.in_bulk(bulk_data.keys())

        new = []
        for id, data in bulk_data.items():
            if id in data_map or not data[0] or not data[1]:
                continue

            con = Constellation(
                id=id,
                name=data[0],
                region_id=data[1],
            )
            new.append(con)
            added += 1

        if new:
            Constellation.objects.bulk_create(new)

        return added

    # -----------------------------------------------------------------------
    # Systems
    def import_system(self):
        added = 0

        self.cursor.execute('SELECT solarSystemID, solarSystemName, constellationID FROM mapSolarSystems')
        bulk_data = {}
        for row in self.cursor:
            id = int(row[0])
            if id:
                bulk_data[id] = row[1:]

        data_map = System.objects.in_bulk(bulk_data.keys())

        new = []
        for id, data in bulk_data.items():
            if id in data_map or not data[0] or not data[1]:
                continue

            system = System(
                id=id,
                name=data[0],
                constellation_id=data[1],
            )
            new.append(system)
            added += 1

        if new:
            System.objects.bulk_create(new)

        return added

    # -----------------------------------------------------------------------
    # Stations
    def import_station(self):
        added = 0

        self.cursor.execute('SELECT stationID, stationName, solarSystemID FROM staStations')
        bulk_data = {}
        for row in self.cursor:
            id = int(row[0])
            if id:
                bulk_data[id] = row[1:]

        data_map = Station.objects.in_bulk(bulk_data.keys())

        new = []
        for id, data in bulk_data.items():
            if id in data_map or not data[0] or not data[1]:
                continue

            station = Station(
                id=id,
                name=data[0],
                system_id=data[1],
            )
            station._make_shorter_name()
            new.append(station)
            added += 1

        if new:
            Station.objects.bulk_create(new)

        return added

    # -----------------------------------------------------------------------
    # Market groups
    def import_marketgroup(self):
        added = 0

        self.cursor.execute('SELECT marketGroupID, marketGroupName, parentGroupID FROM invMarketGroups')
        bulk_data = {}
        for row in self.cursor:
            id = int(row[0])
            if id:
                bulk_data[id] = row[1:]

        data_map = MarketGroup.objects.in_bulk(bulk_data.keys())

        last_count = 999999
        while bulk_data:
            items = list(bulk_data.items())
            if len(items) == last_count:
                print 'infinite loop!'
                for id, data in items:
                    print id, data
                break
            last_count = len(items)

            for id, data in items:
                if data[1] is None:
                    parent = None
                else:
                    # if the parent id doesn't exist yet we have to do this later
                    try:
                        parent = MarketGroup.objects.get(pk=data[1])
                    except MarketGroup.DoesNotExist:
                        continue

                # if we've already added this marketgroup, check that the parent
                # hasn't changed
                mg = data_map.get(id, None)
                if mg is not None:
                    if parent is not None and mg.parent.id != parent.id:
                        mg.delete()
                    else:
                        if mg.name != data[0]:
                            mg.name = data[0]
                            mg.save()
                            print '==> Updated data for #%s (%r)' % (mg.id, mg.name)

                        del bulk_data[id]
                        continue

                mg = MarketGroup(
                    id=id,
                    name=data[0],
                    parent=parent,
                )
                mg.save()
                added += 1

                del bulk_data[id]

        return added

    # -----------------------------------------------------------------------
    # Item Categories
    def import_itemcategory(self):
        added = 0

        self.cursor.execute('SELECT categoryID, categoryName FROM invCategories')
        bulk_data = {}
        for row in self.cursor:
            id = int(row[0])
            if id and row[1]:
                bulk_data[id] = row[1:]

        data_map = ItemCategory.objects.in_bulk(bulk_data.keys())

        new = []
        for id, data in bulk_data.items():
            if id in data_map or not data[0]:
                continue

            ic = ItemCategory(
                id=id,
                name=data[0],
            )
            new.append(ic)
            added += 1

        if new:
            ItemCategory.objects.bulk_create(new)

        return added

    # -----------------------------------------------------------------------
    # Item Groups
    def import_itemgroup(self):
        added = 0

        self.cursor.execute('SELECT groupID, groupName, categoryID FROM invGroups')
        bulk_data = {}
        for row in self.cursor:
            id = int(row[0])
            if id and row[2]:
                bulk_data[id] = row[1:]

        data_map = ItemGroup.objects.in_bulk(bulk_data.keys())

        new = []
        for id, data in bulk_data.items():
            if not data[1]:
                continue

            ig = data_map.get(id, None)
            if ig is not None:
                if ig.name != data[0]:
                    print '==> Renamed %r to %r' % (ig.name, data[0])
                    ig.name = data[0]
                    ig.save()
                continue

            ig = ItemGroup(
                id=id,
                name=data[0],
                category_id=data[1],
            )
            new.append(ig)
            added += 1

        if new:
            ItemGroup.objects.bulk_create(new)

        return added

    # -----------------------------------------------------------------------
    # Items
    def import_item(self):
        added = 0

        self.cursor.execute("""
            SELECT 
                  i.typeID
                , i.typeName
                , i.groupID
                , i.marketGroupID
                , i.portionSize
                , i.volume
                , i.basePrice 
                , COALESCE(dta.valueInt, dta.valueFloat)
            FROM invTypes i
            LEFT JOIN dgmTypeAttributes dta
                ON  dta.typeID      = i.typeID
                AND dta.attributeID = 633
        """)
				
        bulk_data = {}
        mg_ids = set()
        for row in self.cursor:
            bulk_data[int(row[0])] = row[1:]
            if row[3] is not None:
                mg_ids.add(int(row[3]))

        data_map = Item.objects.in_bulk(bulk_data.keys())
        mg_map = MarketGroup.objects.in_bulk(mg_ids)
        new = []
        for id, data in bulk_data.items():

            if not data[0] or not data[1]:
                continue

            if data[2] is None:
                mg_id = None
            else:
                mg_id = int(data[2])
                if mg_id not in mg_map:
                    print '==> Invalid marketGroupID %s' % (mg_id)
                    continue

            portion_size = Decimal(data[3])
            volume = PACKAGED.get(data[1], Decimal(str(data[4])))
            base_price = Decimal(data[5])

            # handle modified items
            item = data_map.get(id, None)
            if item is not None:
                if item.name != data[0] or item.portion_size != portion_size or item.volume != volume or \
                   item.base_price != base_price or item.market_group_id != mg_id or item.meta_level != data[6]:
                    print '==> Updated data for #%s (%r)' % (item.id, item.name)
                    item.name            = data[0]
                    item.portion_size    = portion_size
                    item.volume          = volume
                    item.base_price      = base_price
                    item.market_group_id = mg_id
                    item.meta_level      = data[6]
                    item.save()
                continue

            item = Item(
                id=id,
                name=data[0],
                item_group_id=data[1],
                market_group_id=mg_id,
                portion_size=portion_size,
                volume=volume,
                base_price=base_price,
                meta_level=data[6]
            )
            new.append(item)
            added += 1

        if new:
            Item.objects.bulk_create(new)

        return added

    # -----------------------------------------------------------------------
    def import_blueprint(self):
        # Blueprints
        added = 0

        self.cursor.execute("""
            SELECT  b.blueprintTypeID, t.typeName, b.productTypeID, b.productionTime, b.productivityModifier, b.materialModifier, b.wasteFactor
            FROM    invBlueprintTypes AS b
            INNER JOIN invTypes AS t
            ON      b.blueprintTypeID = t.typeID
            WHERE   t.published = 1
        """)
        bulk_data = {}
        for row in self.cursor:
            bulk_data[int(row[0])] = row[1:]

        data_map = Blueprint.objects.in_bulk(bulk_data.keys())

        new = []
        for id, data in bulk_data.items():
            if not data[0] or not data[1]:
                continue

            bp = data_map.get(id, None)
            if bp is not None:
                if bp.name != data[0]:
                    print '==> Renamed %r to %r' % (bp.name, data[0])
                    bp.name = data[0]
                    bp.save()
            else:
                new.append(Blueprint(
                    id=id,
                    name=data[0],
                    item_id=data[1],
                    production_time=data[2],
                    productivity_modifier=data[3],
                    material_modifier=data[4],
                    waste_factor=data[5],
                ))
                added += 1

        if new:
            Blueprint.objects.bulk_create(new)

        # Collect all components
        new = []
        for id, data in bulk_data.items():
            # Base materials
            self.cursor.execute('SELECT materialTypeID, quantity FROM invTypeMaterials WHERE typeID=%s', (data[1],))
            for baserow in self.cursor:
                new.append(BlueprintComponent(
                    blueprint_id=id,
                    item_id=baserow[0],
                    count=baserow[1],
                    needs_waste=True,
                ))
                added += 1

            # Extra materials. activityID 1 is manufacturing - categoryID 16 is skill requirements
            self.cursor.execute("""
                SELECT  r.requiredTypeID, r.quantity
                FROM    ramTypeRequirements AS r
                INNER JOIN invTypes AS t
                ON      r.requiredTypeID = t.typeID
                INNER JOIN invGroups AS g
                ON      t.groupID = g.groupID
                WHERE   r.typeID = %s
                        AND r.activityID = 1
                        AND g.categoryID <> 16
            """, (id,))

            for extrarow in self.cursor:
                new.append(BlueprintComponent(
                    blueprint_id=id,
                    item_id=extrarow[0],
                    count=extrarow[1],
                    needs_waste=False,
                ))
                added += 1

        # If there's any new ones just drop and recreate the whole lot, easier
        # than trying to work out what has changed for every single blueprint
        if new:
            BlueprintComponent.objects.all().delete()
            BlueprintComponent.objects.bulk_create(new)

        return added

    # -----------------------------------------------------------------------
    # Skills
    def import_skill(self):
        added = 0

        #                    AND invTypes.published = 1
        skills = {}
        self.cursor.execute("""
            SELECT  DISTINCT invTypes.typeID,
                    dgmTypeAttributes.valueFloat AS rank,
                    invTypes.description
            FROM    invTypes
            INNER JOIN invGroups ON (invTypes.groupID = invGroups.groupID)
            INNER JOIN dgmTypeAttributes ON (invTypes.typeID = dgmTypeAttributes.typeID)
            WHERE   invGroups.categoryID = 16
                    AND dgmTypeAttributes.attributeID = 275
                    AND dgmTypeAttributes.valueFloat IS NOT NULL
                    AND invTypes.marketGroupID IS NOT NULL
            ORDER BY invTypes.typeID
        """)
        for row in self.cursor:
            # Handle NULL descriptions
            if row[2] is None:
                desc = ''
            else:
                desc = row[2].strip()

            skills[row[0]] = {
                'rank': int(row[1]),
                'description': desc,
            }

        # Primary/secondary attributes
        self.cursor.execute("""
            SELECT  typeID, attributeID, valueInt, valueFloat
            FROM    dgmTypeAttributes
            WHERE   attributeID IN (180, 181)
        """)
        for row in self.cursor:
            # skip unpublished
            skill = skills.get(row[0], None)
            if skill is None:
                continue

            if row[1] == 180:
                k = 'pri'
            else:
                k = 'sec'
            if row[2]:
                skill[k] = row[2]
            else:
                skill[k] = row[3]

        # filter skills I guess
        skill_map = {}
        for skill in Skill.objects.all():
            skill_map[skill.item_id] = skill

        new = []
        for id, data in skills.items():
            # TODO: add value verification
            skill = skill_map.get(id, None)
            if skill is not None:
                if skill.rank != data['rank'] or skill.description != data['description'] or \
                        skill.primary_attribute != data['pri'] or skill.secondary_attribute != data['sec']:
                    skill.rank = data['rank']
                    skill.description = data['description']
                    skill.primary_attribute = data['pri']
                    skill.secondary_attribute = data['sec']
                    skill.save()
                    print '==> Updated skill details for #%d' % (id)
                continue

            new.append(Skill(
                item_id=id,
                rank=data['rank'],
                primary_attribute=data['pri'],
                secondary_attribute=data['sec'],
                description=data['description'],
            ))
            added += 1

        if new:
            Skill.objects.bulk_create(new)

        return added

    # :skills:
    #       :prerequisite: # These are the attribute ids for skill prerequisites. [item, level]
    #         1: [182, 277]
    #         2: [183, 278]
    #         3: [184, 279]
    #         4: [1285, 1286]
    #         5: [1289, 1287]
    #         6: [1290, 1288]
    #       :primary_attribute: 180 # database attribute ID for primary attribute
    #       :secondary_attribute: 181 # database attribute ID for secondary attribute
    #       :attributes: # Mapping of id keys to the actual attribute
    #         165: :intelligence
    #         164: :charisma
    #         166: :memory
    #         167: :perception
    #         168: :willpower

    # -----------------------------------------------------------------------
    # InventoryFlags
    def import_inventoryflag(self):
        added = 0

        self.cursor.execute('SELECT flagID, flagName, flagText FROM invFlags')

        bulk_data = {}
        for row in self.cursor:
            bulk_data[int(row[0])] = row[1:]

        data_map = InventoryFlag.objects.in_bulk(bulk_data.keys())

        new = []
        for id, data in bulk_data.items():
            if not data[0] or not data[1]:
                continue

            # handle renamed flags
            flag = data_map.get(id, None)
            if flag is not None:
                if flag.name != data[0] or flag.text != data[1]:
                    print '==> Renamed %r to %r' % (flag.name, data[0])
                    flag.name = data[0]
                    flag.text = data[1]
                    flag.save()
                continue

            flag = InventoryFlag(
                id=id,
                name=data[0],
                text=data[1],
            )
            new.append(flag)
            added += 1

        if new:
            InventoryFlag.objects.bulk_create(new)

        return added

    # -----------------------------------------------------------------------
    # NPC Factions
    def import_npcfaction(self):
        added = 0

        self.cursor.execute('SELECT factionID, factionName FROM chrFactions')

        bulk_data = {}
        for row in self.cursor:
            bulk_data[int(row[0])] = row[1]

        data_map = Faction.objects.in_bulk(bulk_data.keys())

        new = []
        for id, name in bulk_data.items():
            faction = data_map.get(id, None)
            if faction is not None:
                if faction.name != name:
                    print '==> Renamed %r to %r' % (faction.name, name)
                    faction.name = name
                    faction.save()
                continue

            faction = Faction(
                id=id,
                name=name,
            )
            new.append(faction)
            added += 1

        if new:
            Faction.objects.bulk_create(new)

        return added

    # -----------------------------------------------------------------------
    # NPC Corporations
    def import_npccorporation(self):
        added = 0

        self.cursor.execute("""
            SELECT  c.corporationID, i.itemName
            FROM    crpNPCCorporations c, invNames i
            WHERE   c.corporationID = i.itemID
        """)

        bulk_data = {}
        for row in self.cursor:
            bulk_data[int(row[0])] = row[1]

        data_map = Corporation.objects.in_bulk(bulk_data.keys())

        new = []
        for id, name in bulk_data.items():
            corp = data_map.get(id, None)
            if corp is not None:
                if corp.name != name:
                    print '==> Renamed %r to %r' % (corp.name, name)
                    corp.name = name
                    corp.save()
                continue

            corp = Corporation(
                id=id,
                name=name,
            )
            new.append(corp)
            added += 1

        if new:
            Corporation.objects.bulk_create(new)

        return added


    # -----------------------------------------------------------------------
    # Items prerequisites
    def import_item_prerequisite(self):
        added = 0
 
        # skill prerequisites
        self.cursor.execute("""
            SELECT 
                i.typeID         as itemID, 
                ip.typeID        as prerqSkillID,
                dtal.valueInt    as prerqSkillLevelInt,
                dtal.valueFloat  as prerqSkillLevelFloat
            FROM invGroups g
            LEFT JOIN invTypes i 
                ON i.groupID = g.groupID
            LEFT JOIN dgmTypeAttributes dta
                ON dta.typeID = i.typeID AND
                   dta.attributeID IN (182, 183, 184, 1285, 1289, 1290)
            LEFT JOIN dgmTypeAttributes dtal 
                ON dtal.typeID = dta.typeID AND 
                (
                    (dtal.attributeID = 277 AND dta.attributeID = 182) OR
                    (dtal.attributeID = 278 AND dta.attributeID = 183) OR
                    (dtal.attributeID = 279 AND dta.attributeID = 184) OR
                    (dtal.attributeID = 1286 AND dta.attributeID = 1285) OR
                    (dtal.attributeID = 1287 AND dta.attributeID = 1289) OR
                    (dtal.attributeID = 1288 AND dta.attributeID = 1290)
                )
            JOIN invTypes ip 
                ON ip.typeID = dta.valueInt OR
                   ip.typeID = dta.valueFloat
            
            WHERE i.typeID NOT IN (19430, 9955) 
                AND i.published = 1
                AND g.categoryID NOT IN (0,1,2,3,25)
            ORDER BY g.groupName DESC        
        """)
        
        ItemPrerequisite.objects.all().delete()
        new=[]
        
        for row in self.cursor:
            # if no parent skills, continue
            if row[1] is None:
                continue
            
            # get the item where we'll add some prereq skills
            try:
                item = Item.objects.get(id=row[0])
            except Item.DoesNotExist:
                continue
            
            # get the prereq skill
            try:
                skill = Skill.objects.get(item_id=row[1])
            except Skill.DoesNotExist:
                continue
            
            # get the skill level required
            if row[2]:
                level = row[2]
            else:
                level = row[3]
                
            prereq = ItemPrerequisite(
                item=item,
                skill=skill,
                level=level
            )
            new.append(prereq)
            
            added += 1

        if new:
            ItemPrerequisite.objects.bulk_create(new)

        return added


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    importer = Importer()
    importer.import_all()
