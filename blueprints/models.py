from django.db import models
from django.contrib.auth.models import User

from decimal import *
from everdi.common import commas, nice_time


class Character(models.Model):
	user = models.ForeignKey(User)
	name = models.CharField(max_length=30)
	api_key = models.CharField(max_length=64)
	industry_skill = models.IntegerField(default=0)
	production_efficiency_skill = models.IntegerField(default=0)
	factory_cost = models.DecimalField(max_digits=8, decimal_places=2)
	factory_per_hour = models.DecimalField(max_digits=8, decimal_places=2)
	sales_tax = models.DecimalField(max_digits=4, decimal_places=2)
	brokers_fee = models.DecimalField(max_digits=4, decimal_places=2)
	
	class Meta:
		ordering = ('name',)
	
	def __unicode__(self):
		return self.name

class Item(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=128)
	portion_size = models.IntegerField()
	
	sell_median = models.DecimalField(max_digits=15, decimal_places=2)
	buy_median = models.DecimalField(max_digits=15, decimal_places=2)
	
	class Meta:
		ordering = ('name',)
	
	def __unicode__(self):
		return self.name
	
	def nice_sell_median(self):
		return commas(self.sell_median)

class Blueprint(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=128)
	item = models.ForeignKey(Item)
	components = models.ManyToManyField(Item, through='BlueprintComponent', related_name='components')
	
	production_time = models.IntegerField()
	productivity_modifier = models.IntegerField()
	material_modifier = models.IntegerField()
	waste_factor = models.IntegerField()
	
	class Meta:
		ordering = ('name',)
	
	def __unicode__(self):
		return self.name

class BlueprintComponent(models.Model):
	blueprint = models.ForeignKey(Blueprint)
	item = models.ForeignKey(Item)
	count = models.IntegerField()
	needs_waste = models.BooleanField()

class BlueprintInstance(models.Model):
	character = models.ForeignKey(Character)
	blueprint = models.ForeignKey(Blueprint)
	material_level = models.IntegerField(default=0)
	productivity_level = models.IntegerField(default=0)
	
	class Meta:
		ordering = ('character', 'blueprint')
	
	def __unicode__(self):
		return "%s's %s" % (self.character.name, self.blueprint.name)
	
	def calc_production_time(self, runs=1, fudge_pl=0):
		# PTM = ProductionTimeModifier = (1 - (0.04 * IndustrySkill)) * ImplantModifier * ProductionSlotModifier
		# ProductionTime (PL>=0) = BaseProductionTime * (1 - (ProductivityModifier / BaseProductionTime) * (PL / (1 + PL)) * PTM
		# ProductionTime (PL<0)  = BaseProductionTime * (1 - (ProductivityModifier / BaseProductionTime) * (PL - 1)) * PTM
		PTM = (1 - (Decimal('0.04') * self.character.industry_skill)) # implement implants/production slots
		BPT = Decimal(self.blueprint.production_time)
		BPM = self.blueprint.productivity_modifier
		PL = Decimal(self.productivity_level + fudge_pl)
		
		if PL >= 0:
			pt = BPT * (1 - (BPM / BPT) * (PL / (1 + PL))) * PTM
		else:
			pt = BPT * (1 - (BPM / BPT) * (PL - 1)) * PTM
		
		pt *= runs
		
		return pt.quantize(Decimal('0'), rounding=ROUND_UP)
	
	def nice_production_time(self, runs=1):
		return nice_time(self.calc_production_time(runs=runs))
	
	def calc_production_cost(self, runs=1, fudge_ml=0, use_sell=False, ):
		"""
from everdi.blueprints.models import *
bpi = BlueprintInstance.objects.all()[0]
bpi.calc_production_cost()
cq = BlueprintComponent.objects.filter(blueprint=bpi.blueprint)
PES = bpi.character.production_efficiency_skill
ML = bpi.material_level
WF = bpi.blueprint.waste_factor
		"""
		
		total_cost = Decimal(0)
		
		# Calculate component costs
		PES = self.character.production_efficiency_skill
		ML = self.material_level + fudge_ml
		WF = self.blueprint.waste_factor
		
		component_queryset = BlueprintComponent.objects.filter(blueprint=self.blueprint)
		for component in component_queryset:
			CC = component.count
			if component.needs_waste:
				amt = round(CC * (1 + ((WF / 100.0) / (ML + 1)) + (0.25 - (0.05 * PES))))
			else:
				amt = CC
			
			amt *= runs
			
			if use_sell is True:
				total_cost += (Decimal(str(amt)) * component.item.sell_median)
			else:
				total_cost += (Decimal(str(amt)) * component.item.buy_median)
		
		# Calculate factory costs
		total_cost += self.character.factory_cost
		
		PT = self.calc_production_time(runs=runs)
		total_cost += (self.character.factory_per_hour * (PT / 3600))
		
		# Calculate taxes and fees
		total_cost = total_cost * (1 + (self.character.sales_tax / 100)) * (1 + (self.character.brokers_fee / 100))
		
		# Run count
		total_cost /= (self.blueprint.item.portion_size * runs)
		
		return total_cost.quantize(Decimal('.01'), rounding=ROUND_UP)
	
	def nice_production_cost(self, runs=1, use_sell=False):
		return commas(self.calc_production_cost(runs=runs, use_sell=use_sell))
	
	#def nice_production_cost_sell(self):
	#	return commas(self.calc_production_cost(use_sell=True))
