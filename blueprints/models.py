from django.db import models
from django.contrib.auth.models import User

from decimal import *


class Character(models.Model):
	user = models.ForeignKey(User)
	name = models.CharField(max_length=30)
	api_key = models.CharField(max_length=64)
	industry_skill = models.IntegerField()
	production_efficiency_skill = models.IntegerField()
	factory_cost = models.DecimalField(max_digits=8, decimal_places=2)
	factory_per_hour = models.DecimalField(max_digits=8, decimal_places=2)
	sales_tax = models.DecimalField(max_digits=4, decimal_places=2)
	brokers_fee = models.DecimalField(max_digits=4, decimal_places=2)
	
	def __unicode__(self):
		return self.name

class Item(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=128)
	portion_size = models.IntegerField()
	
	sell_median = models.DecimalField(max_digits=15, decimal_places=2)
	buy_median = models.DecimalField(max_digits=15, decimal_places=2)
	
	def __unicode__(self):
		return self.name

class Blueprint(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=128)
	item = models.ForeignKey(Item)
	components = models.ManyToManyField(Item, through='BlueprintComponent', related_name='components')
	
	production_time = models.IntegerField()
	productivity_modifier = models.IntegerField()
	material_modifier = models.IntegerField()
	waste_factor = models.IntegerField()
	
	def __unicode__(self):
		return self.name
	
	class Meta:
		ordering = ('name',)

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
		ordering = ('blueprint',)
	
	def __unicode__(self):
		return "%s's %s" % (self.character.name, self.blueprint.name)
	
	def calc_production_time(self):
		# PTM = ProductionTimeModifier = (1 - (0.04 * IndustrySkill)) * ImplantModifier * ProductionSlotModifier
		# ProductionTime (PE>=0) = BaseProductionTime * (1 - (ProductivityModifier / BaseProductionTime) * (PE / (1 + PE)) * PTM
		# ProductionTime (PE<0)  = BaseProductionTime * (1 - (ProductivityModifier / BaseProductionTime) * (PE - 1)) * PTM
		PTM = (1 - (Decimal('0.04') * self.character.industry_skill)) # implement implants/production slots
		BPT = self.blueprint.production_time
		PE = self.productivity_level
		
		if PE >= 0:
			pt = BPT * (1 - (PTM / BPT) * (PE / (1 + PE))) * PTM
		else:
			pt = BPT * (1 - (PTM / BPT) * (PE - 1)) * PTM
		
		return pt.quantize(Decimal('0'), rounding=ROUND_UP)
	
	def nice_production_time(self):
		pt = self.calc_production_time()
		
		m, s = divmod(pt, 60)
		h, m = divmod(m, 60)
		d, h = divmod(h, 24)
		
		parts = []
		if d:
			parts.append('%dd' % (d))
		if h:
			parts.append('%dh' % (h))
		if m:
			parts.append('%dm' % (m))
		if s:
			parts.append('%ds' % (s))
		
		return ' '.join(parts)
	
	def calc_production_cost(self):
		"""
from everdi.blueprints.models import *
bpi = BlueprintInstance.objects.all()[0]
bpi.calc_production_cost()
cq = BlueprintComponent.objects.filter(blueprint=bpi.blueprint)
PES = bpi.character.production_efficiency_skill
ME = bpi.material_level
WF = bpi.blueprint.waste_factor
		"""
		
		total_cost = Decimal(0)
		
		# Calculate component costs
		PES = self.character.production_efficiency_skill
		ME = self.material_level
		WF = self.blueprint.waste_factor
		
		component_queryset = BlueprintComponent.objects.filter(blueprint=self.blueprint)
		for component in component_queryset:
			CC = component.count
			if component.needs_waste:
				amt = round(CC * (1 + ((WF / 100.0) / (ME + 1)) + (0.25 - (0.05 * PES))))
				#if ME >= 0:
				#	ME_waste = round(CC * (WF / 100.0) * (1 / (ME + 1)))
				#else:
				#	amt = round(CC * (1 + ((WF / 100.0) / (ME + 1)) + (0.25 - (0.05 * PES))))
				#	ME_waste = round(CC * (WF / 100.0) * (1 - ME))
				
				#skill_waste = round(CC * (0.04 * self.character.production_efficiency_skill))
				#amt = CC + ME_waste + skill_waste
			
			else:
				amt = CC
			
			total_cost += (Decimal(str(amt)) * component.item.buy_median)
		
		# Calculate factory costs
		total_cost += self.character.factory_cost
		
		PT = self.calc_production_time()
		total_cost += (self.character.factory_per_hour * (PT / 3600))
		
		# Calculate taxes and fees
		total_cost = total_cost * (1 + (self.character.sales_tax / 100)) * (1 + (self.character.brokers_fee / 100))
		
		# Run count
		print total_cost, self.blueprint.item.portion_size
		total_cost /= self.blueprint.item.portion_size
		print total_cost
		
		return total_cost.quantize(Decimal('.01'), rounding=ROUND_UP)
