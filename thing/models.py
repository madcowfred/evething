from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg, Sum

import datetime
import time
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
	
	sales_tax = models.DecimalField(max_digits=3, decimal_places=2)
	brokers_fee = models.DecimalField(max_digits=3, decimal_places=2)
	
	eve_user_id = models.IntegerField(verbose_name='User ID', default=0)
	eve_api_key = models.CharField(max_length=64, verbose_name='API key', default='zzz')
	eve_api_corp = models.BooleanField(verbose_name='Use API key for corp?', default=True)
	eve_character_id = models.IntegerField(default=0)
	
	class Meta:
		ordering = ('name',)
	
	def __unicode__(self):
		return self.name

# Categories
class ItemCategory(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=64)

# Groups
class ItemGroup(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=64)
	category = models.ForeignKey(ItemCategory)

# Items
class Item(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=128)
	group = models.ForeignKey(ItemGroup)
	
	portion_size = models.IntegerField()
	# 0.0025 -> 10,000,000,000
	volume = models.DecimalField(max_digits=16, decimal_places=4, default=0)
	
	sell_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
	buy_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
	
	def __unicode__(self):
		return self.name
	
	def get_volume(self, days=7):
		iph_days = self.itempricehistory_set.all()[:days]
		agg = self.itempricehistory_set.filter(pk__in=iph_days).aggregate(Sum('movement'))
		if agg['movement__sum'] is None:
			return Decimal('0')
		else:
			return Decimal(str(agg['movement__sum']))

# Historical item price data
class ItemPriceHistory(models.Model):
	item = models.ForeignKey(Item)
	date = models.DateField()
	average = models.DecimalField(max_digits=15, decimal_places=2)
	maximum = models.DecimalField(max_digits=15, decimal_places=2)
	minimum = models.DecimalField(max_digits=15, decimal_places=2)
	movement = models.BigIntegerField()
	orders = models.IntegerField()
	
	class Meta:
		ordering = ('-date',)
	
	def __unicode__(self):
		return '%s (%s)' % (self.item, self.date)

# Station
numeral_map = zip(
	(1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1),
	('M', 'CM', 'D', 'CD', 'C', 'XC', 'L', 'XL', 'X', 'IX', 'V', 'IV', 'I')
)
def roman_to_int(n):
	n = unicode(n).upper()
	
	i = result = 0
	for integer, numeral in numeral_map:
		while n[i:i + len(numeral)] == numeral:
			result += integer
			i += len(numeral)
	return result

class Station(models.Model):
	id = models.IntegerField(primary_key=True)
	name = models.CharField(max_length=128)
	short_name = models.CharField(max_length=64, blank=True, null=True)
	
	def __unicode__(self):
		return self.name
	
	# Build the short name when this object is saved
	def save(self, *args, **kwargs):
		self._make_shorter_name()
		super(Station, self).save(*args, **kwargs)
	
	def _make_shorter_name(self):
		out = []
		
		parts = self.name.split(' - ')
		if len(parts) == 1:
			self.short_name = self.name
		else:
			a_parts = parts[0].split()
			# Change the roman annoyance to a proper digit
			out.append('%s %s' % (a_parts[0], str(roman_to_int(a_parts[1]))))
			
			# Moooon
			if parts[1].startswith('Moon'):
				out[0] = '%s-%s' % (out[0], parts[1][5:])
				out.append(''.join(s[0] for s in parts[2].split()))
			else:
				out.append(''.join(s[0] for s in parts[1].split()))
			
			self.short_name = ' - '.join(out)

# Time frames
class Timeframe(models.Model):
	corporation = models.ForeignKey(Corporation)
	
	title = models.CharField(max_length=32)
	slug = models.SlugField(max_length=32)
	start_date = models.DateTimeField()
	end_date = models.DateTimeField()
	
	class Meta:
		ordering = ('title',)
	
	def __unicode__(self):
		return self.title

# Wallet transactions
class Transaction(models.Model):
	id = models.BigIntegerField(primary_key=True)
	corporation = models.ForeignKey(Corporation)
	corp_wallet = models.ForeignKey(CorpWallet)
	character = models.ForeignKey(Character)
	
	date = models.DateTimeField(db_index=True)
	t_type = models.CharField(max_length=1, choices=((u'B', u'Buy'), (u'S', u'Sell')))
	station = models.ForeignKey(Station)
	item = models.ForeignKey(Item)
	quantity = models.IntegerField()
	price = models.DecimalField(max_digits=14, decimal_places=2)
	total_price = models.DecimalField(max_digits=17, decimal_places=2)

# Market orders
# http://wiki.eve-id.net/APIv2_Corp_MarketOrders_XML
class Order(models.Model):
	id = models.BigIntegerField(primary_key=True)
	
	corporation = models.ForeignKey(Corporation)
	corp_wallet = models.ForeignKey(CorpWallet)
	character = models.ForeignKey(Character)
	station = models.ForeignKey(Station)
	item = models.ForeignKey(Item)
	
	issued = models.DateTimeField()
	o_type = models.CharField(max_length=1, choices=((u'B', u'Buy'), (u'S', u'Sell')))
	volume_entered = models.IntegerField()
	volume_remaining = models.IntegerField()
	min_volume = models.IntegerField()
	duration = models.IntegerField()
	escrow = models.DecimalField(max_digits=17, decimal_places=2)
	price = models.DecimalField(max_digits=14, decimal_places=2)
	total_price = models.DecimalField(max_digits=17, decimal_places=2)
	
	class Meta:
		ordering = ('-o_type', 'item__name')
	
	def get_expiry_date(self):
		return self.issued + datetime.timedelta(self.duration)

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
	bp_type = models.CharField(max_length=1, choices=((u'C', u'Copy'), (u'O', u'Original')))
	material_level = models.IntegerField(default=0)
	productivity_level = models.IntegerField(default=0)
	
	class Meta:
		ordering = ('bp_type', 'blueprint')
	
	def __unicode__(self):
		return "%s's %s (%s, ML%s PL%s)" % (self.character.name, self.blueprint.name, self.get_bp_type_display(),
			self.material_level, self.productivity_level)
	
	# Calculate production time, taking PL and skills into account
	def calc_production_time(self, runs=1):
		# PTM = ProductionTimeModifier = (1 - (0.04 * IndustrySkill)) * ImplantModifier * ProductionSlotModifier
		# ProductionTime (PL>=0) = BaseProductionTime * (1 - (ProductivityModifier / BaseProductionTime) * (PL / (1 + PL)) * PTM
		# ProductionTime (PL<0)  = BaseProductionTime * (1 - (ProductivityModifier / BaseProductionTime) * (PL - 1)) * PTM
		PTM = (1 - (Decimal('0.04') * self.character.industry_skill)) # FIXME:implement implants/production slot modifiers
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
	def calc_production_cost(self, runs=1, use_sell=False, components=None):
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
		total_cost += self.character.factory_cost
		total_cost += (self.character.factory_per_hour * (self.calc_production_time(runs=runs) / 3600))
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
		
		component_queryset = BlueprintComponent.objects.filter(blueprint=self.blueprint).select_related()
		for component in component_queryset:
			if component.needs_waste:
				amt = round(component.count * (1 + ((WF / 100.0) / (ML + 1)) + (0.25 - (0.05 * PES))))
			else:
				amt = component.count
			
			comps.append((component.item, int(amt * runs)))
		
		return comps
