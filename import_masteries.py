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

# Set up our environment and import settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'evething.settings'
from django.db import connections

from thing.models.skill import Skill
from thing.models.skillplan import SkillPlan
from thing.models.spentry import SPEntry
from thing.models.spskill import SPSkill
from thing.helpers import roman


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
        time_func('Masteries', self.import_masteries)

    # -----------------------------------------------------------------------
    def import_masteries(self):
        # Masteries
        added = 0

        # Delete existing mastery skillplans
        SkillPlan.objects.filter(visibility=SkillPlan.MASTERY_VISIBILITY).delete()

        self.cursor.execute("""
            SELECT s.skillID, s.skillLevel, m.masteryLevel, t.typeID, t.typeName
            FROM certSkills AS s
            JOIN certMasteries AS m ON s.certId = m.certID AND s.certLevelInt = m.masteryLevel
            JOIN invTypes AS t on m.typeId = t.typeID
        """)

        ship_masteries = {}
        for row in self.cursor:
            if row[1] > 0:
                if row[3] not in ship_masteries:
                    ship_masteries[row[3]] = {
                        'typeID': row[3],
                        'name': row[4],
                        'masteries': {}
                    }
                if row[2] not in ship_masteries[row[3]]['masteries']:
                    ship_masteries[row[3]]['masteries'][row[2]] = {}

                if row[0] in ship_masteries[row[3]]['masteries'][row[2]]:
                    if row[1] > ship_masteries[row[3]]['masteries'][row[2]][row[0]]:
                        ship_masteries[row[3]]['masteries'][row[2]][row[0]] = row[1]
                else:
                    ship_masteries[row[3]]['masteries'][row[2]][row[0]] = row[1]

        for type_id in ship_masteries:
            entries = []
            for mastery_level in ship_masteries[type_id]['masteries']:
                print('==> Created Plan: %s - Mastery %s' % (ship_masteries[type_id]['name'], roman(mastery_level + 1)))

                skillplan = SkillPlan.objects.create(
                    name='%s - Mastery %s' % (ship_masteries[type_id]['name'], roman(mastery_level + 1)),
                    visibility=SkillPlan.MASTERY_VISIBILITY
                )

                seen = {}
                position = 0

                for skill_id in ship_masteries[type_id]['masteries'][mastery_level]:
                    level = ship_masteries[type_id]['masteries'][mastery_level][skill_id]

                    # Get prereqs
                    prereqs = Skill.get_prereqs(skill_id)
                    for pre_skill_id, pre_level in prereqs:
                        for i in range(seen.get(pre_skill_id, 0) + 1, pre_level + 1):
                            # print('\t%d:\t%d' % (pre_skill_id, i))

                            try:
                                sps = SPSkill.objects.create(
                                    skill_id=pre_skill_id,
                                    level=i,
                                    priority=3,
                                )
                            except:
                                continue

                            entries.append(SPEntry(
                                skill_plan=skillplan,
                                position=position,
                                sp_skill=sps,
                            ))

                            position += 1
                            seen[pre_skill_id] = i

                    # Add the actual skill
                    for i in range(seen.get(skill_id, 0) + 1, level + 1):
                        # print('\t%d:\t%d' % (skill_id, i))
                        try:
                            sps = SPSkill.objects.create(
                                skill_id=skill_id,
                                level=i,
                                priority=3,
                            )
                        except:
                            continue

                        entries.append(SPEntry(
                            skill_plan=skillplan,
                            position=position,
                            sp_skill=sps,
                        ))

                        position += 1
                        seen[skill_id] = i

                added += 1
            SPEntry.objects.bulk_create(entries)

        return added

# ---------------------------------------------------------------------------

if __name__ == '__main__':
    importer = Importer()
    importer.import_all()
