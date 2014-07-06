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

from decimal import Decimal, ROUND_UP

from django.contrib.auth.models import User
from django.db import models

from thing.models.blueprint import Blueprint
from thing.models.blueprintcomponent import BlueprintComponent


class BlueprintInstance(models.Model):
    """Blueprint instances - an owned blueprint"""
    user = models.ForeignKey(User, blank=True, null=True)
    blueprint = models.ForeignKey(Blueprint)

    original = models.BooleanField()
    material_level = models.IntegerField(default=0)
    productivity_level = models.IntegerField(default=0)

    class Meta:
        app_label = 'thing'
        ordering = ('blueprint',)

    def __unicode__(self):
        if self.original:
            return "%s (BPO, ML%s PL%s)" % (self.blueprint.name, self.material_level, self.productivity_level)
        else:
            return "%s (BPC, ML%s PL%s)" % (self.blueprint.name, self.material_level, self.productivity_level)

    # Calculate production time, taking PL and skills into account
    # TODO: fix this, skills not available
    # TODO: take implants into account
    def calc_production_time(self, runs=1):
        # PTM = ProductionTimeModifier = (1 - (0.04 * IndustrySkill)) * ImplantModifier * ProductionSlotModifier
        # ProductionTime (PL>=0) = BaseProductionTime * (1 - (ProductivityModifier / BaseProductionTime) * (PL / (1 + PL)) * PTM
        # ProductionTime (PL<0)  = BaseProductionTime * (1 - (ProductivityModifier / BaseProductionTime) * (PL - 1)) * PTM
        PTM = (1 - (Decimal('0.04') * 5))  # self.character.industry_skill))  # FIXME:implement implants/production slot modifiers
        BPT = Decimal(self.blueprint.production_time)
        BPM = self.blueprint.productivity_modifier
        PL = Decimal(self.productivity_level)

        if PL >= 0:
            pt = BPT * (1 - (BPM / BPT) * (PL / (1 + PL))) * PTM
        else:
            pt = BPT * (1 - (BPM / BPT) * (PL - 1)) * PTM

        pt *= runs

        return pt.quantize(Decimal('0'), rounding=ROUND_UP)

    # Calculate the construction cost assuming ME50 components
    def calc_capital_production_cost(self):
        total_cost = Decimal(0)

        components = self._get_components()
        child_ids = []
        counts = {}
        for component, count in components:
            child_ids.append(component.id)
            counts[component] = count

        comp_comps = {}
        for child_comp in BlueprintComponent.objects.select_related().filter(blueprint__item__in=child_ids):
            comp_comps.setdefault(child_comp.blueprint, []).append((child_comp.item, child_comp.count))

        for bp, bp_comps in comp_comps.items():
            bpi = BlueprintInstance(
                user=self.user,
                blueprint=bp,
                original=True,
                material_level=50,
                productivity_level=0,
            )
            cost = bpi.calc_production_cost(components=bp_comps) * counts[bp.item]
            total_cost += cost

        return total_cost

    # Calculate production cost, taking ML and skills into account
    # TODO: fix this, skills not available
    # TODO: move factory cost/etc to a model attached to the User table
    def calc_production_cost(self, components=None, runs=1, use_sell=False, character=None):
        total_cost = Decimal(0)

        # Component costs
        if components is None:
            components = self._get_components(runs=runs)

        for item, amt in components:
            if use_sell is True:
                total_cost += (Decimal(str(amt)) * item.sell_price)
            else:
                total_cost += (Decimal(str(amt)) * item.buy_price)

        # Factory costs
        # if character is not None:
        #     total_cost += character.factory_cost
        #     total_cost += (character.factory_per_hour * (self.calc_production_time(runs=runs) / 3600))
        #     # Sales tax
        #     total_cost *= (1 + (character.sales_tax / 100))
        #     # Broker's fee
        #     total_cost *= (1 + (character.brokers_fee / 100))

        # Run count
        total_cost /= (self.blueprint.item.portion_size * runs)

        return total_cost.quantize(Decimal('.01'), rounding=ROUND_UP)

    # Get all components required for this item, adjusted for ML and relevant skills
    # TODO: fix this, skills aren't currently available
    def _get_components(self, components=None, runs=1):
        PES = 5  # fixme: self.character.production_efficiency_skill
        ML = self.material_level
        WF = self.blueprint.waste_factor / 100.0

        comps = []

        if components is None:
            components = BlueprintComponent.objects.filter(blueprint=self.blueprint).select_related()

        for component in components:
            if component.needs_waste:
                # well this is horrible
                if self.material_level >= 0:
                    amt = round(component.count * (1 + (WF / (ML + 1)) + (0.25 - (0.05 * PES))))
                else:
                    amt = round(component.count * (1 + (WF * (abs(ML) + 1))) + (0.25 - (0.05 * PES)))
            else:
                amt = component.count

            comps.append((component.item, int(amt * runs)))

        return comps

# ------------------------------------------------------------------------------
