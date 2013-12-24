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

from decimal import Decimal

from django.db import models
from django.db.models import Sum

from thing.models.itemgroup import ItemGroup
from thing.models.marketgroup import MarketGroup

from thing.models.itemprerequisite import ItemPrerequisite


# ------------------------------------------------------------------------------

class Item(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=128)

    item_group = models.ForeignKey(ItemGroup)
    market_group = models.ForeignKey(MarketGroup, blank=True, null=True, related_name='items')

    portion_size = models.IntegerField()
    # 0.0025 -> 10,000,000,000
    volume = models.DecimalField(max_digits=16, decimal_places=4, default=0)

    base_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sell_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    buy_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        app_label = 'thing'
        #ordering = ('meta','name')

    def __unicode__(self):
        return self.name

    def get_volume(self, days=7):
        iph_days = self.pricehistory_set.all()[:days]
        agg = self.pricehistory_set.filter(pk__in=iph_days).aggregate(Sum('movement'))
        if agg['movement__sum'] is None:
            return Decimal('0')
        else:
            return Decimal(str(agg['movement__sum']))

    # ------------------------------------------------------------------------------
    # Item Prerequisite methods
    
    # dict of all prerequisites for a given item    
    prerequisite_list = None
    
    def add_prerequisite(self, skill, level):
        prereq_skill, created = ItemPrerequisite.objects.get_or_create(
            item=self,
            skill=skill,
            level=level)
        return prereq_skill
    
    def remove_prerequisite(self, skill):
        ItemPrerequisite.objects.filter(
            item=self,
            skill=skill).delete()
        return self
    
    def clean_prerequisites(self):
        ItemPrerequisite.objects.filter(
            item=self).delete()
        return self

    def get_prerequisites(self):
        """
        Return the "first level" of prerequisites.
        """
        return ItemPrerequisite.objects.filter(
            item=self)

    def get_flat_prerequisites(self):
        prerequisites = self.get_prerequisites()
        skill_list = []
        if prerequisites is None:
            return skill_list
            
        for itemprereq in prerequisites:
            prereq_skill = itemprereq.skill
            
            # get prereq of the current parent
            skill_list.extend(prereq_skill.item.get_flat_prerequisites())
            
            # and add the skill into the list too
            skill_list.append((prereq_skill.item_id, itemprereq.level))
            
        return skill_list


    def is_prerequisite(self, skill, level): 
        """
        Return true if a given skill at a given level is a prerequisite of the current item
        """

        if self.prerequisite_list is None:
            self.prerequisite_list = Item.get_all_prerequisites(self)
        
        if skill.item_id in self.prerequisite_list and self.prerequisite_list[skill.item_id] >= level:
            return True
        return False
        
    # ------------------------------------------------------------------------------
    # static methods
    
    @staticmethod
    def get_all_prerequisites(item):
        'Get all the prerequisites of a given item (search in all dependencies)'
        
        # return a list of ItemPrerequisite
        prereqs = item.get_prerequisites()
        
        if prereqs is None:
            return dict()
        
        list_prereqs=dict()
        
        for itemprereq in prereqs:
            list_prereqs[itemprereq.skill.item_id] = itemprereq.level
            
            for skill_id,level in Item.get_all_prerequisites(itemprereq.skill.item).items():
                if skill_id in list_prereqs: 
                    list_prereqs[skill_id] = max(list_prereqs[skill_id], level)
                else:
                    list_prereqs[skill_id] = level
        
        return list_prereqs

# ------------------------------------------------------------------------------
