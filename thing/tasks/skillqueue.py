from .apitask import APITask

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
        SkillQueueModel.objects.filter(character=character).delete()

        # Create any new SkillQueue objects
        if new:
            SkillQueueModel.objects.bulk_create(new)

        return True

# ---------------------------------------------------------------------------
