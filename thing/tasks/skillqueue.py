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

from thing import queries
from thing.models import Character, Skill
from thing.models import SkillQueue as SkillQueueModel

# ---------------------------------------------------------------------------

class SkillQueue(APITask):
    name = 'thing.skill_queue'

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

        # Gather info
        rows = []
        skill_ids = set()
        for row in self.root.findall('result/rowset/row'):
            if row.attrib['startTime'] and row.attrib['endTime']:
                skill_ids.add(int(row.attrib['typeID']))
                rows.append(row)

        skill_map = Skill.objects.in_bulk(skill_ids)

        # Add new skills
        new = []
        for row in rows:
            skill_id = int(row.attrib['typeID'])
            skill = skill_map.get(skill_id)
            if skill is None:
                self.log_warn("Skill %s does not exist!", skill_id)
                continue

            new.append(SkillQueueModel(
                character=character,
                skill=skill,
                start_time=self.parse_api_date(row.attrib['startTime']),
                end_time=self.parse_api_date(row.attrib['endTime']),
                start_sp=row.attrib['startSP'],
                end_sp=row.attrib['endSP'],
                to_level=row.attrib['level'],
            ))

        # Delete the old queue
        cursor = self.get_cursor()
        cursor.execute(queries.skillqueue_delete, [character_id])
        cursor.close()

        # Create any new SkillQueue objects
        if new:
            SkillQueueModel.objects.bulk_create(new)

        return True

# ---------------------------------------------------------------------------
