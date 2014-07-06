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

import math

from django.db import models
from django.db import models
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
    
from thing.models.item import Item
from thing.models.itemprerequisite import ItemPrerequisite



class Skill(models.Model):
    CHARISMA_ATTRIBUTE = 164
    INTELLIGENCE_ATTRIBUTE = 165
    MEMORY_ATTRIBUTE = 166
    PERCEPTION_ATTRIBUTE = 167
    WILLPOWER_ATTRIBUTE = 168
    ATTRIBUTE_CHOICES = (
        (CHARISMA_ATTRIBUTE, 'Cha'),
        (INTELLIGENCE_ATTRIBUTE, 'Int'),
        (MEMORY_ATTRIBUTE, 'Mem'),
        (PERCEPTION_ATTRIBUTE, 'Per'),
        (WILLPOWER_ATTRIBUTE, 'Wil'),
    )

    ATTRIBUTE_MAP = {
        CHARISMA_ATTRIBUTE: ('cha_attribute', 'cha_bonus'),
        INTELLIGENCE_ATTRIBUTE: ('int_attribute', 'int_bonus'),
        MEMORY_ATTRIBUTE: ('mem_attribute', 'mem_bonus'),
        PERCEPTION_ATTRIBUTE: ('per_attribute', 'per_bonus'),
        WILLPOWER_ATTRIBUTE: ('wil_attribute', 'wil_bonus'),
    }

    item = models.OneToOneField(Item, primary_key=True)
    rank = models.SmallIntegerField()
    description = models.TextField()
    primary_attribute = models.SmallIntegerField(choices=ATTRIBUTE_CHOICES)
    secondary_attribute = models.SmallIntegerField(choices=ATTRIBUTE_CHOICES)

    
    class Meta:
        app_label = 'thing'
        
    def __unicode__(self):
        return '%s (Rank %d; %s/%s)' % (self.item.name, self.rank, self.get_primary_attribute_display(),
                                        self.get_secondary_attribute_display())

    def __html__(self):
        return "<strong>Primary:</strong> %s / <strong>Secondary</strong>: %s<br><br>%s" % (
            self.get_primary_attribute_display(),
            self.get_secondary_attribute_display(),
            self.description.replace('\n', '<br>'),
        )

    def get_sp_at_level(self, level=5):
        if level == 0:
            return 0
        else:
            return int(math.ceil(2 ** ((2.5 * level) - 2.5) * 250 * self.rank))

    def get_sp_per_minute(self, character, force_bonus=None):
        pri_attrs = Skill.ATTRIBUTE_MAP[self.primary_attribute]
        sec_attrs = Skill.ATTRIBUTE_MAP[self.secondary_attribute]

        if force_bonus is None:
            pri = getattr(character.details, pri_attrs[0]) + getattr(character.details, pri_attrs[1])
            sec = getattr(character.details, sec_attrs[0]) + getattr(character.details, sec_attrs[1])
        else:
            pri = getattr(character.details, pri_attrs[0]) + force_bonus
            sec = getattr(character.details, sec_attrs[0]) + force_bonus

        return pri + (sec / 2.0)

    def get_sppm_stats(self, stats, implants):
        pri_attrs = Skill.ATTRIBUTE_MAP[self.primary_attribute]
        sec_attrs = Skill.ATTRIBUTE_MAP[self.secondary_attribute]

        pri = stats.get(pri_attrs[0]) + implants.get(pri_attrs[1])
        sec = stats.get(sec_attrs[0]) + implants.get(sec_attrs[1])

        return pri + (sec / 2.0)
    

    # Item Prerequisite methods
    
    # dict of all unlocked item for a given skill and level    
    unlocked_list = None
    
    # return the list of item that need the skill as a prerequisite
    def get_items_unlocked_by_skill(self, level=1):
        return ItemPrerequisite.objects.filter(
            skill=self,
            level__gte=level)
        
    def is_unlocked_by_skill(self, item, level):
        """
        Return true if the given item is unlocked by the current skill at the given level
        """

        if self.unlocked_list is None:
            self.unlocked_list = dict()
        
        if level not in self.unlocked_list:
            self.unlocked_list[level] = Skill.get_all_items_unlocked_by_skill(self,level)

        if item.id in self.unlocked_list[level]:
            return True
        return False

    
    @staticmethod
    def get_all_items_unlocked_by_skill(skill, level):
        """
            Get all the items unlocked by a skill at a given level 
        """
        
        # return a list of ItemPrerequisite
        unlocked_items = skill.get_items_unlocked_by_skill(level)
        if unlocked_items is None:
            return {}
        
        list_unlocked_item=set()
        
        for itemprereq in unlocked_items:
            # add the item found (can be a skill or something else)
            list_unlocked_item.add(itemprereq.item_id)
            
            # if it's a skill, we need to dig deeper
            try:
                skill_unlocked = Skill.objects.get(item__id=itemprereq.item_id)
                
            except Skill.DoesNotExist:
                continue 

            list_unlocked_item.update(Skill.get_all_items_unlocked_by_skill(skill_unlocked,1))
        
        return list_unlocked_item

# ------------------------------------------------------------------------------
