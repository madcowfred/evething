from django.db import models
from django.contrib.auth.models import User


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
	material_level = models.IntegerField()
	productivity_level = models.IntegerField()
	
	def __unicode__(self):
		return "%s's %s" % (self.character.name, self.blueprint.name)
	
	class Meta:
		ordering = ('blueprint',)
