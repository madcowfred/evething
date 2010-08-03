from django.db import models
from django.contrib.auth.models import User

from decimal import *

# Corporation
class Corporation(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=64)
	
	class Meta:
		ordering = ('name',)
	
	def __unicode__(self):
		return self.name
	
	def get_total_balance(self):
		return self.corpwallet_set.aggregate(Sum('balance'))['balance_sum']

# Corporation wallets
class CorpWallet(models.Model):
	account_id = models.IntegerField(primary_key=True)
	corporation = models.ForeignKey(Corporation)
	account_key = models.IntegerField()
	balance = models.DecimalField(max_digits=18, decimal_places=2)

# Character
class Character(models.Model):
	user = models.ForeignKey(User)
	
	name = models.CharField(max_length=30)
	corporation = models.ForeignKey(Corporation)
	
	industry_skill = models.IntegerField(default=0)
	production_efficiency_skill = models.IntegerField(default=0)
	
	factory_cost = models.DecimalField(max_digits=8, decimal_places=2)
	factory_per_hour = models.DecimalField(max_digits=8, decimal_places=2)
	
	sales_tax = models.DecimalField(max_digits=4, decimal_places=2)
	brokers_fee = models.DecimalField(max_digits=4, decimal_places=2)
	
	eve_user_id = models.IntegerField(blank=True, verbose_name='User ID')
	eve_api_key = models.CharField(max_length=64, blank=True, verbose_name='API key')
	eve_character_id = models.IntegerField(default=0)
	
	class Meta:
		ordering = ('name',)
	
	def __unicode__(self):
		return self.name

# Items
ITEM_NAME_SHORT = (
	('Beta Reactor Control', 'BRC'),
	('Local Hull Conversion', 'LHC'),
	('Local Power Plant Manager', 'LPPM'),
)
class Item(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=128)
	portion_size = models.IntegerField()
	
	sell_median = models.DecimalField(max_digits=15, decimal_places=2, default=0)
	buy_median = models.DecimalField(max_digits=15, decimal_places=2, default=0)
	
	def __unicode__(self):
		return self.name
	
	def shorter_name(self):
		for orig, rep in ITEM_NAME_SHORT:
			if self.name.startswith(orig):
				return self.name.replace(orig, rep, 1)
		return self.name

# Station
class Station(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=128)

# Wallet transactions
class Transaction(models.Model):
	id = models.IntegerField(primary_key=True)
	corporation = models.ForeignKey(Corporation)
	corp_wallet = models.ForeignKey(CorpWallet)
	
	date = models.DateTimeField()
	t_type = models.CharField(max_length=1, choices=((u'B', u'Buy'), (u'S', u'Sell')))
	station = models.ForeignKey(Station)
	item = models.ForeignKey(Item)
	quantity = models.IntegerField()
	price = models.DecimalField(max_digits=14, decimal_places=2)
	total_price = models.DecimalField(max_digits=17, decimal_places=2)

# Blueprints
class Blueprint(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=128)
	item = models.ForeignKey(Item)
	#components = models.ManyToManyField(Item, through='BlueprintComponent', related_name='components')
	
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
	needs_waste = models.BooleanField(default=True)

class BlueprintInstance(models.Model):
	character = models.ForeignKey(Character)
	blueprint = models.ForeignKey(Blueprint)
	material_level = models.IntegerField(default=0)
	productivity_level = models.IntegerField(default=0)
	
	class Meta:
		ordering = ('character', 'blueprint')
	
	def __unicode__(self):
		return "%s's %s" % (self.character.name, self.blueprint.name)
	
	# Calculate production time, taking PL and skills into account
	def calc_production_time(self, runs=1):
		# PTM = ProductionTimeModifier = (1 - (0.04 * IndustrySkill)) * ImplantModifier * ProductionSlotModifier
		# ProductionTime (PL>=0) = BaseProductionTime * (1 - (ProductivityModifier / BaseProductionTime) * (PL / (1 + PL)) * PTM
		# ProductionTime (PL<0)  = BaseProductionTime * (1 - (ProductivityModifier / BaseProductionTime) * (PL - 1)) * PTM
		PTM = (1 - (Decimal('0.04') * self.character.industry_skill)) # implement implants/production slots
		BPT = Decimal(self.blueprint.production_time)
		BPM = self.blueprint.productivity_modifier
		PL = Decimal(self.productivity_level)
		
		if PL >= 0:
			pt = BPT * (1 - (BPM / BPT) * (PL / (1 + PL))) * PTM
		else:
			pt = BPT * (1 - (BPM / BPT) * (PL - 1)) * PTM
		
		pt *= runs
		
		return pt.quantize(Decimal('0'), rounding=ROUND_UP)
	
	# Calculate production cost, taking ML and skills into account
	def calc_production_cost(self, runs=1, use_sell=False, ):
		total_cost = Decimal(0)
		
		# Component costs
		for item, amt in self._get_components(runs=runs):
			if use_sell is True:
				total_cost += (Decimal(str(amt)) * item.sell_median)
			else:
				total_cost += (Decimal(str(amt)) * item.buy_median)
		
		# Factory costs
		total_cost += self.character.factory_cost
		
		PT = self.calc_production_time(runs=runs)
		total_cost += (self.character.factory_per_hour * (PT / 3600))
		
		# Sales tax
		total_cost *= (1 + (self.character.sales_tax / 100))
		# Broker's fee
		total_cost *= (1 + (self.character.brokers_fee / 100))
		
		# Run count
		total_cost /= (self.blueprint.item.portion_size * runs)
		
		return total_cost.quantize(Decimal('.01'), rounding=ROUND_UP)
	
	# Get all components required for this item, adjusted for ML and relevant skills
	def _get_components(self, runs=1):
		PES = self.character.production_efficiency_skill
		ML = self.material_level
		WF = self.blueprint.waste_factor
		
		comps = []
		
		component_queryset = BlueprintComponent.objects.filter(blueprint=self.blueprint)
		for component in component_queryset:
			CC = component.count
			if component.needs_waste:
				amt = round(CC * (1 + ((WF / 100.0) / (ML + 1)) + (0.25 - (0.05 * PES))))
			else:
				amt = CC
			
			comps.append((component.item, amt))
		
		return comps
