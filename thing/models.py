from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q, Avg, Sum
from mptt.models import MPTTModel, TreeForeignKey

import datetime
import math
import time
from decimal import *

# ---------------------------------------------------------------------------
# API keys
class APIKey(models.Model):
    ACCOUNT_TYPE = 'Account'
    CHARACTER_TYPE = 'Character'
    CORPORATION_TYPE = 'Corporation'
    
    user = models.ForeignKey(User)
    
    id = models.IntegerField(primary_key=True, verbose_name='Key ID')
    vcode = models.CharField(max_length=64, verbose_name='Verification code')
    name = models.CharField(max_length=64)
    
    access_mask = models.BigIntegerField(null=True, blank=True)
    key_type = models.CharField(max_length=16, null=True, blank=True)
    expires = models.DateTimeField(null=True, blank=True)
    valid = models.BooleanField(default=True)
    
    # this is only used for corporate keys, ugh
    corp_character = models.ForeignKey('Character', null=True, blank=True, related_name='corporate_apikey')
    
    paid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('id',)
    
    def __unicode__(self):
        return '#%s (%s)' % (self.id, self.key_type)

    def get_masked_vcode(self):
        return '%s%s%s' % (self.vcode[:4], '*' * 16, self.vcode[-4:])

# API cache entries
class APICache(models.Model):
    url = models.URLField()
    parameters = models.CharField(max_length=1024)
    cached_until = models.DateTimeField()
    text = models.TextField()

# ---------------------------------------------------------------------------
# Corporations
class Corporation(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    ticker = models.CharField(max_length=5, blank=True, null=True)
    
    class Meta:
        ordering = ('name',)
    
    def __unicode__(self):
        return '%s [%s]' % (self.name, self.ticker)
    
    def get_total_balance(self):
        return self.corpwallet_set.aggregate(Sum('balance'))['balance_sum']

# ---------------------------------------------------------------------------
# Corporation wallets
class CorpWallet(models.Model):
    account_id = models.IntegerField(primary_key=True)
    corporation = models.ForeignKey(Corporation)
    account_key = models.IntegerField()
    description = models.CharField(max_length=64)
    balance = models.DecimalField(max_digits=18, decimal_places=2)
    
    class Meta:
        ordering = ('corporation', 'account_id')
    
    def __unicode__(self):
        return '%s [%s] %s' % (self.corporation.name, self.account_key, self.description)

# ---------------------------------------------------------------------------
# Characters
class Character(models.Model):
    apikey = models.ForeignKey(APIKey, null=True, blank=True)
    
    eve_character_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    corporation = models.ForeignKey(Corporation)
    
    wallet_balance = models.DecimalField(max_digits=18, decimal_places=2)
    
    cha_attribute = models.SmallIntegerField()
    int_attribute = models.SmallIntegerField()
    mem_attribute = models.SmallIntegerField()
    per_attribute = models.SmallIntegerField()
    wil_attribute = models.SmallIntegerField()
    cha_bonus = models.SmallIntegerField()
    int_bonus = models.SmallIntegerField()
    mem_bonus = models.SmallIntegerField()
    per_bonus = models.SmallIntegerField()
    wil_bonus = models.SmallIntegerField()
    
    clone_name = models.CharField(max_length=32)
    clone_skill_points= models.IntegerField()

    skills = models.ManyToManyField('Skill', related_name='learned_by', through='CharacterSkill')
    skill_queue = models.ManyToManyField('Skill', related_name='training_by', through='SkillQueue')
    
    # industry stuff
    factory_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    factory_per_hour = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    sales_tax = models.DecimalField(max_digits=3, decimal_places=2, default=1.0)
    brokers_fee = models.DecimalField(max_digits=3, decimal_places=2, default=1.0)
    
    class Meta:
       ordering = ('name',)
    
    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ('character', (), {
            'character_name': self.name,
            }
        )

    def get_total_skill_points(self):
        return CharacterSkill.objects.filter(character=self).aggregate(total_sp=Sum('points'))['total_sp']

class CharacterConfig(models.Model):
    character = models.OneToOneField(Character, unique=True, primary_key=True, related_name='config')

    is_public = models.BooleanField()
    show_clone = models.BooleanField()
    show_implants = models.BooleanField()
    show_skill_queue = models.BooleanField()
    show_wallet = models.BooleanField()

    def __unicode__(self):
        return self.character.name

# Character skills
class CharacterSkill(models.Model):
    character = models.ForeignKey('Character')
    skill = models.ForeignKey('Skill')
    
    level = models.SmallIntegerField()
    points = models.IntegerField()

    def __unicode__(self):
        return '%s: %s (%s; %s SP)' % (self.character, self.skill.item.name, self.level, self.points)
    
    def get_roman_level(self):
        return ['', 'I', 'II', 'III', 'IV', 'V'][self.level]

# Skill queue
class SkillQueue(models.Model):
    character = models.ForeignKey('Character')
    skill = models.ForeignKey('Skill')
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    start_sp = models.IntegerField()
    end_sp = models.IntegerField()
    to_level = models.SmallIntegerField()
    
    def __unicode__(self):
        return '%s: %s %d, %d -> %d - Start: %s, End: %s' % (self.character.name, self.skill.item.name,
            self.to_level, self.start_sp, self.end_sp, self.start_time, self.end_time)

    class Meta:
        ordering = ('start_time',)
    
    def get_complete_percentage(self, now=None):
        if now is None:
            now = datetime.datetime.utcnow()
        remaining = (self.end_time - now).total_seconds()
        remain_sp = remaining / 60.0 * self.skill.get_sp_per_minute(self.character)
        required_sp = self.skill.get_sp_at_level(self.to_level) - self.skill.get_sp_at_level(self.to_level - 1)

        return round(100 - (remain_sp / required_sp * 100), 1)
    
    def get_roman_level(self):
        return ['', 'I', 'II', 'III', 'IV', 'V'][self.to_level]

    def get_remaining(self):
        remaining = (self.end_time - datetime.datetime.utcnow()).total_seconds()
        return int(remaining)

# ---------------------------------------------------------------------------
# Regions
class Region(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    
    def __unicode__(self):
        return self.name
    
    class Meta:
        ordering = ('name'),

# Constellations
class Constellation(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    
    region = models.ForeignKey(Region)
    
    def __unicode__(self):
        return self.name
    
    class Meta:
        ordering = ('name'),

# Systems
class System(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=32)
    
    constellation = models.ForeignKey(Constellation)
    
    def __unicode__(self):
        return self.name
    
    class Meta:
        ordering = ('name'),

# ---------------------------------------------------------------------------
# Stations
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
    
    system = models.ForeignKey(System)
    
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

# ---------------------------------------------------------------------------
# Market groups
class MarketGroup(MPTTModel):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    
    parent = TreeForeignKey('self', blank=True, null=True, related_name='children')
    
    def __unicode__(self):
        return '%s' % (self.name)
    
    class MPTTMeta:
        order_insertion_by = ['name']

# ---------------------------------------------------------------------------
# Item categories
class ItemCategory(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)

# ---------------------------------------------------------------------------
# Item groups
class ItemGroup(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    category = models.ForeignKey(ItemCategory)

# ---------------------------------------------------------------------------
# Items
class Item(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=128)
    
    item_group = models.ForeignKey(ItemGroup)
    market_group = models.ForeignKey(MarketGroup, blank=True, null=True)
    
    portion_size = models.IntegerField()
    # 0.0025 -> 10,000,000,000
    volume = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    
    sell_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    buy_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    def __unicode__(self):
        return self.name
    
    def get_volume(self, days=7):
        iph_days = self.pricehistory_set.all()[:days]
        agg = self.pricehistory_set.filter(pk__in=iph_days).aggregate(Sum('movement'))
        if agg['movement__sum'] is None:
            return Decimal('0')
        else:
            return Decimal(str(agg['movement__sum']))

# ---------------------------------------------------------------------------
# Skills
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
    primary_attribute = models.SmallIntegerField(choices=ATTRIBUTE_CHOICES)
    secondary_attribute = models.SmallIntegerField(choices=ATTRIBUTE_CHOICES)

    def __unicode__(self):
        return '%s (Rank %d; %s/%s)' % (self.item.name, self.rank, self.get_primary_attribute_display(),
            self.get_secondary_attribute_display())

    def get_sp_at_level(self, level=5):
        if level == 0:
            return 0
        else:
            return int(math.ceil(2 ** ((2.5 * level) - 2.5) * 250 * self.rank))

    def get_sp_per_minute(self, character):
        pri_attrs = Skill.ATTRIBUTE_MAP[self.primary_attribute]
        sec_attrs = Skill.ATTRIBUTE_MAP[self.secondary_attribute]

        pri = getattr(character, pri_attrs[0]) + getattr(character, pri_attrs[1])
        sec = getattr(character, sec_attrs[0]) + getattr(character, sec_attrs[1])

        return pri + (sec / 2.0)

# ---------------------------------------------------------------------------
# Historical item price data
class PriceHistory(models.Model):
    region = models.ForeignKey(Region)
    item = models.ForeignKey(Item)
    
    date = models.DateField()
    minimum = models.DecimalField(max_digits=18, decimal_places=2)
    maximum = models.DecimalField(max_digits=18, decimal_places=2)
    average = models.DecimalField(max_digits=18, decimal_places=2)
    movement = models.BigIntegerField()
    orders = models.IntegerField()
    
    class Meta:
        ordering = ('-date',)
        unique_together = ('region', 'item', 'date')
    
    def __unicode__(self):
        return '%s (%s)' % (self.item, self.date)

# ---------------------------------------------------------------------------
# Time frames
# TODO: rename this and implement (character, corp_wallet) assignment somehow
class Campaign(models.Model):
    user = models.ForeignKey(User)
    
    title = models.CharField(max_length=32)
    slug = models.SlugField(max_length=32)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    corp_wallets = models.ManyToManyField(CorpWallet, blank=True, null=True)
    characters = models.ManyToManyField(Character, blank=True, null=True)
    
    class Meta:
        ordering = ('title',)
    
    def __unicode__(self):
        return self.title
    
    def get_transactions_filter(self, transactions):
        return transactions.filter(
            Q(corp_wallet__in=self.corp_wallets.all()) |
            (
                Q(corp_wallet=None) &
                Q(character__in=self.characters.all())
            ),
            date__range=(self.start_date, self.end_date),
        )

# ---------------------------------------------------------------------------
# Wallet transactions
class Transaction(models.Model):
    station = models.ForeignKey(Station)
    character = models.ForeignKey(Character)
    item = models.ForeignKey(Item)
    
    corp_wallet = models.ForeignKey(CorpWallet, null=True, blank=True)
    
    transaction_id = models.BigIntegerField()
    date = models.DateTimeField(db_index=True)
    buy_transaction = models.BooleanField()
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=14, decimal_places=2)
    total_price = models.DecimalField(max_digits=17, decimal_places=2)

# ---------------------------------------------------------------------------
# Market orders
class MarketOrder(models.Model):
    order_id = models.BigIntegerField(primary_key=True)
    
    station = models.ForeignKey(Station)
    item = models.ForeignKey(Item)
    character = models.ForeignKey(Character)
    corp_wallet = models.ForeignKey(CorpWallet, null=True, blank=True)
    
    escrow = models.DecimalField(max_digits=14, decimal_places=2)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    total_price = models.DecimalField(max_digits=17, decimal_places=2)
    
    buy_order = models.BooleanField()
    volume_entered = models.IntegerField()
    volume_remaining = models.IntegerField()
    minimum_volume = models.IntegerField()
    issued = models.DateTimeField(db_index=True)
    expires = models.DateTimeField(db_index=True)
    
    class Meta:
        ordering = ('buy_order', 'item__name')

# ---------------------------------------------------------------------------
# class Asset(models.Model):
#     HANGAR_FLAG = 4
#     CARGO_FLAG = 5
#     LOW_SLOT_1_FLAG = 11
#     LOW_SLOT_2_FLAG = 12
#     LOW_SLOT_3_FLAG = 13
#     LOW_SLOT_4_FLAG = 14
#     LOW_SLOT_5_FLAG = 15
#     LOW_SLOT_6_FLAG = 16
#     LOW_SLOT_7_FLAG = 17
#     LOW_SLOT_8_FLAG = 18
#     MID_SLOT_1_FLAG = 19
#     MID_SLOT_2_FLAG = 20
#     MID_SLOT_3_FLAG = 21
#     MID_SLOT_4_FLAG = 22
#     MID_SLOT_5_FLAG = 23
#     MID_SLOT_6_FLAG = 24
#     MID_SLOT_7_FLAG = 25
#     MID_SLOT_8_FLAG = 26
#     HIGH_SLOT_1_FLAG = 27
#     HIGH_SLOT_2_FLAG = 28
#     HIGH_SLOT_3_FLAG = 29
#     HIGH_SLOT_4_FLAG = 30
#     HIGH_SLOT_5_FLAG = 31
#     HIGH_SLOT_6_FLAG = 32
#     HIGH_SLOT_7_FLAG = 33
#     HIGH_SLOT_8_FLAG = 34

#     id = models.BigIntegerField(primary_key=True)

#     character = models.ForeignKey(Character, blank=True, null=True)
#     corporation = models.ForeignKey(Character, blank=True, null=True)

#     item = models.ForeignKey(Item)
#     system = models.ForeignKey(System, blank=True, null=True)
#     station = models.ForeignKey(Station, blank=True, null=True)

#     container = models.ForeignKey('self', blank=True, null=True, related_name='contents')

#     flag = models.IntegerField()
#     quantity = models.BigIntegerField()


# ---------------------------------------------------------------------------
# Industry jobs
# fixme: implement POS support, oh god
#class IndustryJob(models.Model):
#    job_id = models.IntegerField()
#    station_id = models.ForeignKeyField(Station)
#    
#    install_time = models.DateTimeField()
#    begin_time = models.DateTimeField()
#    end_time = models.DateTimeField()

# ---------------------------------------------------------------------------
# Blueprints
class Blueprint(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=128)
    item = models.ForeignKey(Item)
    
    production_time = models.IntegerField()
    productivity_modifier = models.IntegerField()
    material_modifier = models.IntegerField()
    waste_factor = models.IntegerField()
    
    components = models.ManyToManyField(Item, related_name='component_of', through='BlueprintComponent')
    
    class Meta:
        ordering = ('name',)
    
    def __unicode__(self):
        return self.name

# ---------------------------------------------------------------------------
# Blueprint components
class BlueprintComponent(models.Model):
    blueprint = models.ForeignKey(Blueprint)
    item = models.ForeignKey(Item)
    
    count = models.IntegerField()
    needs_waste = models.BooleanField(default=True)

# ---------------------------------------------------------------------------
# Blueprint instances - an owned blueprint
class BlueprintInstance(models.Model):
    user = models.ForeignKey(User)
    blueprint = models.ForeignKey(Blueprint)
    
    original = models.BooleanField()
    material_level = models.IntegerField(default=0)
    productivity_level = models.IntegerField(default=0)
    
    class Meta:
        ordering = ('blueprint',)#.item',)
    
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
        PTM = (1 - (Decimal('0.04') * 5))#self.character.industry_skill)) # FIXME:implement implants/production slot modifiers
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
        if character is not None:
            total_cost += character.factory_cost
            total_cost += (character.factory_per_hour * (self.calc_production_time(runs=runs) / 3600))
            # Sales tax
            total_cost *= (1 + (character.sales_tax / 100))
            # Broker's fee
            total_cost *= (1 + (character.brokers_fee / 100))
        
        # Run count
        total_cost /= (self.blueprint.item.portion_size * runs)
        
        return total_cost.quantize(Decimal('.01'), rounding=ROUND_UP)
    
    # Get all components required for this item, adjusted for ML and relevant skills
    # TODO: fix this, skills aren't currently available
    def _get_components(self, components=None, runs=1):
        PES = 5 #fixme: self.character.production_efficiency_skill
        ML = self.material_level
        WF = self.blueprint.waste_factor
        
        comps = []
        
        if components is None:
            components = BlueprintComponent.objects.filter(blueprint=self.blueprint).select_related(depth=1)
        
        for component in components:
            if component.needs_waste:
                amt = round(component.count * (1 + ((WF / 100.0) / (ML + 1)) + (0.25 - (0.05 * PES))))
            else:
                amt = component.count
            
            comps.append((component.item, int(amt * runs)))
        
        return comps
