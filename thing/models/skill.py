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

import cPickle
import math

from django.db import models
from django.db import models
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
    


from thing.models.item import Item
from thing.models.skillparent import SkillParent


# ------------------------------------------------------------------------------

try:
    SKILL_MAP = cPickle.load(open('skill_map.pickle', 'r'))
except:
    SKILL_MAP = {}

# ------------------------------------------------------------------------------

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

    parents = models.ManyToManyField('self'
                                    , blank=True
                                    , null=True
                                    , through="SkillParent"
                                    , related_name="children"
                                    , symmetrical=False)


    # only used with is_xxx. Else it's not required to init these.
    children_list = None
    parents_list = None
    
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
    

    def add_parent(self, skill, level):
        parent_skill, created = SkillParent.objects.get_or_create(
            child_skill=self,
            parent_skill=skill,
            level=level)
        return parent_skill
    
    def remove_parent(self, skill):
        SkillParent.objects.filter(
            child_skill=self,
            parent_skill=skill).delete()
        return self
    
    def clean_parents(self):
        SkillParent.objects.filter(
            child_skill=self).delete()
        return self

    def get_skill_parent(self):
        return SkillParent.objects.filter(
            child_skill=self)
            
    def get_skill_children(self, level=1):
        return SkillParent.objects.filter(
            parent_skill=self,
            level__gte=level)
        
    def is_child(self, skill, level):
        """
        Check if the current skill at level "level" has "skill" as a child
        """

        if self.children_list is None:
            self.children_list = OrderedDict()
        
        if level not in self.children_list:
            self.children_list[level] = Skill.get_all_children(self,level)

        if skill.item.id in self.children_list[level]:
            return True
        return False


    def is_parent(self, skill, level): 
        """
        Check if the current skill has "skill" at level "level" as a parent
        """

        if self.parents_list is None:
            self.parents_list = Skill.get_all_parents(self)
        
        if skill.item.id in self.parents_list and self.parents_list[skill.item.id] >= level:
            return True
        return False
        
    # ------------------------------------------------------------------------------

    @staticmethod
    def get_prereqs(skill_id):
        'Get all pre-requisite skills for a given skill ID'

        def _recurse_prereqs(prereqs, skill):
            for sid, level in SKILL_MAP.get(skill, {}).values():
                prereqs.append([sid, level])
                _recurse_prereqs(prereqs, sid)

        prereqs = []
        _recurse_prereqs(prereqs, skill_id)

        # Return a reversed list so it's in training order
        return list(reversed(prereqs))
        
    @staticmethod
    def get_all_parents(skill):
        'Get all the parents of a given skill'
        
        parents = skill.get_skill_parent()
        if parents is None:
            return OrderedDict()
        
        list_parent=OrderedDict()
        
        for parent in parents:
            list_parent[parent.parent_skill.item.id] = parent.level
            
            for skill_id,level in Skill.get_all_parents(parent.parent_skill).items():
                if skill_id in list_parent: 
                    list_parent[skill_id] = max(list_parent[skill_id], level)
                else:
                    list_parent[skill_id] = level
        
        return list_parent

    @staticmethod
    def get_all_children(skill, level):
        """
            Get all the parents of a given skill
            
            skill : the skill used to get the children 
            level : the level of the skill (children depend on the parent level)
        """
        
        children = skill.get_skill_children(level)
        if children is None:
            return {}
        
        list_children=set()
        
        for child in children:
            list_children.add(child.child_skill.item.id)
            list_children.update(Skill.get_all_children(child.child_skill,1))
        
        return list_children

# ------------------------------------------------------------------------------
