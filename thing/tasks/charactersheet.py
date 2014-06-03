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

from thing.models import Character, CharacterSkill, Skill


class CharacterSheet(APITask):
    name = 'thing.character_sheet'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return

        try:
            character = Character.objects.select_related('details').get(pk=character_id)
        except Character.DoesNotExist:
            self.log_warn('Character %s does not exist!', character_id)
            return

        # Fetch the API data
        params = {'characterID': character_id}
        if self.fetch_api(url, params) is False or self.root is None:
            return

        # Update wallet balance
        character.details.wallet_balance = self.root.findtext('result/balance', '0')

        # Update attributes
        character.details.cha_attribute = self.root.findtext('result/attributes/charisma')
        character.details.int_attribute = self.root.findtext('result/attributes/intelligence')
        character.details.mem_attribute = self.root.findtext('result/attributes/memory')
        character.details.per_attribute = self.root.findtext('result/attributes/perception')
        character.details.wil_attribute = self.root.findtext('result/attributes/willpower')

        # Update attribute bonuses :ccp:
        enh = self.root.find('result/attributeEnhancers')
        character.details.cha_bonus = enh.findtext('charismaBonus/augmentatorValue', '0')
        character.details.int_bonus = enh.findtext('intelligenceBonus/augmentatorValue', '0')
        character.details.mem_bonus = enh.findtext('memoryBonus/augmentatorValue', '0')
        character.details.per_bonus = enh.findtext('perceptionBonus/augmentatorValue', '0')
        character.details.wil_bonus = enh.findtext('willpowerBonus/augmentatorValue', '0')

        # Update clone information
        character.details.clone_skill_points = self.root.findtext('result/cloneSkillPoints', '900000')
        character.details.clone_name = self.root.findtext('result/cloneName', 'Clone Grade Alpha')

        # Save character details
        character.details.save()

        # Get all of the rowsets
        rowsets = self.root.findall('result/rowset')

        # First rowset is skills
        skills = {}
        for row in rowsets[0]:
            skills[int(row.attrib['typeID'])] = (int(row.attrib['skillpoints']), int(row.attrib['level']))

        # Grab any already existing skills
        for char_skill in CharacterSkill.objects.select_related('item', 'skill').filter(character=character, skill__in=skills.keys()):
            skill_id = char_skill.skill.item_id

            # Warn about missing skill IDs
            if skill_id not in skills:
                self.log_warn("Character %s had Skill %s go missing", character_id, skill_id)
                char_skill.delete()
                continue

            points, level = skills[skill_id]
            if char_skill.points != points or char_skill.level != level:
                char_skill.points = points
                char_skill.level = level
                char_skill.save()

            del skills[skill_id]

        # Fetch skill objects
        skill_map = Skill.objects.in_bulk(skills.keys())

        # Add any leftovers
        new = []
        for skill_id, (points, level) in skills.items():
            skill = skill_map.get(skill_id, None)
            if skill is None:
                self.log_warn("Skill %s does not exist", skill_id)
                continue

            new.append(CharacterSkill(
                character=character,
                skill=skill,
                points=points,
                level=level,
            ))

        # Insert new skills
        if new:
            CharacterSkill.objects.bulk_create(new)

        return True
