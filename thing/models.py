from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q, Avg, Sum
from django.db.models.signals import post_save
from mptt.models import MPTTModel, TreeForeignKey

import datetime
import math
import time
from decimal import *

from thing.stuff import total_seconds

# ---------------------------------------------------------------------------
# Profile information for a user
class UserProfile(models.Model):
    HOME_SORT_ORDERS = (
        ('apiname', 'APIKey name'),
        ('charname', 'Character name'),
        ('corpname', 'Corporation name'),
        ('totalsp', 'Total SP'),
        ('wallet', 'Wallet balance'),
    )

    user = models.OneToOneField(User)

    last_seen = models.DateTimeField(default=datetime.datetime.now)

    # User can add APIKeys
    can_add_keys = models.BooleanField(default=True)

    # Global options
    theme = models.CharField(max_length=32, default='default')
    icon_theme = models.CharField(max_length=32, default='default')
    show_clock = models.BooleanField(default=True)
    show_assets = models.BooleanField(default=True)
    show_blueprints = models.BooleanField(default=True)
    show_contracts = models.BooleanField(default=True)
    show_industry = models.BooleanField(default=True)
    show_orders = models.BooleanField(default=True)
    show_trade = models.BooleanField(default=True)
    show_transactions = models.BooleanField(default=True)
    show_wallet_journal = models.BooleanField(default=True)
    show_market_scan = models.BooleanField(default=True)

    show_item_icons = models.BooleanField(default=False)
    entries_per_page = models.IntegerField(default=100)

    # Home view options
    home_chars_per_row = models.IntegerField(default=4)
    home_sort_order = models.CharField(choices=HOME_SORT_ORDERS, max_length=12, default='apiname')
    home_sort_descending = models.BooleanField(default=False)
    home_hide_characters = models.TextField(default='')
    home_show_locations = models.BooleanField(default=True)

# Magical hook so this gets called when a new user is created
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

post_save.connect(create_user_profile, sender=User)

# ---------------------------------------------------------------------------
# API keys
class APIKey(models.Model):
    ACCOUNT_TYPE = 'Account'
    CHARACTER_TYPE = 'Character'
    CORPORATION_TYPE = 'Corporation'

    API_KEY_INFO_MASK = 0

    CHAR_ACCOUNT_STATUS_MASK = 33554432
    CHAR_ASSET_LIST_MASK = 2
    CHAR_CHARACTER_INFO_MASK = 16777216
    CHAR_CHARACTER_SHEET_MASK = 8
    CHAR_CONTRACTS_MASK = 67108864
    CHAR_INDUSTRY_JOBS_MASK = 128
    CHAR_LOCATIONS_MASK = 134217728
    CHAR_MARKET_ORDERS_MASK = 4096
    CHAR_SKILL_QUEUE_MASK = 262144
    CHAR_STANDINGS_MASK = 524288
    CHAR_WALLET_JOURNAL_MASK = 2097152
    CHAR_WALLET_TRANSACTIONS_MASK = 4194304

    MASKS_CHAR = (
        CHAR_ACCOUNT_STATUS_MASK,
        CHAR_ASSET_LIST_MASK,
        CHAR_CHARACTER_INFO_MASK,
        CHAR_CHARACTER_SHEET_MASK,
        CHAR_CONTRACTS_MASK,
        CHAR_INDUSTRY_JOBS_MASK,
        CHAR_LOCATIONS_MASK,
        CHAR_MARKET_ORDERS_MASK,
        CHAR_SKILL_QUEUE_MASK,
        CHAR_STANDINGS_MASK,
        CHAR_WALLET_JOURNAL_MASK,
        CHAR_WALLET_TRANSACTIONS_MASK,
    )

    CORP_ACCOUNT_BALANCE_MASK = 1
    CORP_ASSET_LIST_MASK = 2
    CORP_CONTRACTS_MASK = 8388608
    CORP_CORPORATION_SHEET_MASK = 8
    CORP_INDUSTRY_JOBS_MASK = 128
    CORP_MARKET_ORDERS_MASK = 4096
    CORP_WALLET_JOURNAL_MASK = 1048576
    CORP_WALLET_TRANSACTIONS_MASK = 2097152

    MASKS_CORP = (
        CORP_ACCOUNT_BALANCE_MASK,
        CORP_ASSET_LIST_MASK,
        CORP_CONTRACTS_MASK,
        CORP_CORPORATION_SHEET_MASK,
        CORP_INDUSTRY_JOBS_MASK,
        CORP_MARKET_ORDERS_MASK,
        CORP_WALLET_JOURNAL_MASK,
        CORP_WALLET_TRANSACTIONS_MASK,
    )

    user = models.ForeignKey(User)
    
    keyid = models.IntegerField(verbose_name='Key ID')
    vcode = models.CharField(max_length=64, verbose_name='Verification code')
    name = models.CharField(max_length=64)
    
    valid = models.BooleanField(default=True)

    access_mask = models.BigIntegerField(null=True, blank=True)
    key_type = models.CharField(max_length=16, null=True, blank=True)
    expires = models.DateTimeField(null=True, blank=True)
    paid_until = models.DateTimeField(null=True, blank=True)
    
    characters = models.ManyToManyField('Character', related_name='apikeys')
    
    # this is only used for corporate keys, ugh
    corp_character = models.ForeignKey('Character', null=True, blank=True, related_name='corporate_apikey')
    
    class Meta:
        ordering = ('keyid',)
    
    def __unicode__(self):
        return '#%s, keyId: %s (%s)' % (self.id, self.keyid, self.key_type)

    def get_key_info(self):
        return '%s,%s' % (self.keyid, self.vcode)

    def get_masked_vcode(self):
        return '%s%s%s' % (self.vcode[:4], '*' * 16, self.vcode[-4:])

    def get_remaining_time(self):
        if self.paid_until:
            return max(total_seconds(self.paid_until - datetime.datetime.utcnow()), 0)
        else:
            return 0

    def get_masks(self):
        if self.access_mask is None:
            return []
        elif self.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
            return [mask for mask in self.MASKS_CHAR if self.access_mask & mask == mask]
        elif self.key_type == APIKey.CORPORATION_TYPE:
            return [mask for mask in self.MASKS_CORP if self.access_mask & mask == mask]
        else:
            return []

    # Mark this key as invalid
    def invalidate(self):
        self.valid = False
        self.save()

    # Delete ALL related data for this key
    def purge_data(self):
        self.invalidate()

        from celery.execute import send_task
        send_task('thing.tasks.purge_data', args=[self.id], kwargs={}, queue='et_high')

# ---------------------------------------------------------------------------
# APIKey permanent failure log
class APIKeyFailure(models.Model):
    user = models.ForeignKey(User)
    keyid = models.IntegerField()

    fail_time = models.DateTimeField(db_index=True)
    fail_reason = models.CharField(max_length=255)

# ---------------------------------------------------------------------------
# Task state
class TaskState(models.Model):
    READY_STATE = 0
    QUEUED_STATE = 1
    ACTIVE_STATE = 2
    STATES = (
        (READY_STATE, 'Ready'),
        (QUEUED_STATE, 'Queued'),
        (ACTIVE_STATE, 'Active'),
    )

    key_info = models.CharField(max_length=80, db_index=True)
    url = models.CharField(max_length=64, db_index=True)
    parameter = models.IntegerField()
    state = models.IntegerField(db_index=True)

    mod_time = models.DateTimeField(db_index=True)
    next_time = models.DateTimeField(db_index=True)

    # Are we ready to queue?
    def queue_now(self, now):
        return ((self.state == self.READY_STATE) and self.next_time <= now)

# ---------------------------------------------------------------------------
# Task summaries
class TaskSummary(models.Model):
    ymdh = models.DateTimeField(db_index=True)
    count = models.IntegerField()

# ---------------------------------------------------------------------------
# API cache entries
class APICache(models.Model):
    url = models.URLField()
    parameters = models.TextField()
    text = models.TextField()

    cached_until = models.DateTimeField()
    completed_ok = models.BooleanField(default=False)
    error_displayed = models.BooleanField(default=False)

    # called when the API call completes successfully
    def completed(self):
        self.completed_ok = True
        #self.text = ''
        self.save()

# ---------------------------------------------------------------------------
# Events
class Event(models.Model):
    user = models.ForeignKey(User)
    issued = models.DateTimeField()
    text = models.TextField()

    class Meta:
        ordering = ('-issued', '-id')

    def get_age(self):
        return total_seconds(datetime.datetime.now() - self.issued)

# ---------------------------------------------------------------------------
# Factions
class Faction(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)

# ---------------------------------------------------------------------------
# Alliances
class Alliance(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    short_name = models.CharField(max_length=5)

# ---------------------------------------------------------------------------
# Corporations
class Corporation(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    ticker = models.CharField(max_length=5, blank=True, null=True)

    alliance = models.ForeignKey(Alliance, blank=True, null=True)

    division1 = models.CharField(max_length=64, blank=True, null=True)
    division2 = models.CharField(max_length=64, blank=True, null=True)
    division3 = models.CharField(max_length=64, blank=True, null=True)
    division4 = models.CharField(max_length=64, blank=True, null=True)
    division5 = models.CharField(max_length=64, blank=True, null=True)
    division6 = models.CharField(max_length=64, blank=True, null=True)
    division7 = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        ordering = ('name',)
    
    def __unicode__(self):
        return self.name
    
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
class SimpleCharacter(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)

    def __unicode__(self):
        return self.name

class Character(models.Model):
    id = models.IntegerField(primary_key=True)
    
    name = models.CharField(max_length=64)
    corporation = models.ForeignKey(Corporation, blank=True, null=True)

    # Skill stuff
    skills = models.ManyToManyField('Skill', related_name='learned_by', through='CharacterSkill')
    skill_queue = models.ManyToManyField('Skill', related_name='training_by', through='SkillQueue')
    
    # Standings stuff
    faction_standings = models.ManyToManyField('Faction', related_name='has_standings', through='FactionStanding')
    corporation_standings = models.ManyToManyField('Corporation', related_name='has_standings', through='CorporationStanding')

    # industry stuff
    #factory_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    #factory_per_hour = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    #sales_tax = models.DecimalField(max_digits=3, decimal_places=2, default=1.5)
    #brokers_fee = models.DecimalField(max_digits=3, decimal_places=2, default=1.0)
    
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

    def get_short_clone_name(self):
        if self.details.clone_name:
            return self.details.clone_name.replace('Clone Grade ', '')
        else:
            return 'Unknown'

    def get_total_skill_points(self):
        return CharacterSkill.objects.filter(character=self).aggregate(total_sp=Sum('points'))['total_sp']

# Character configuration information
class CharacterConfig(models.Model):
    character = models.OneToOneField(Character, unique=True, primary_key=True, related_name='config')

    is_public = models.BooleanField(default=False)
    show_clone = models.BooleanField(default=False)
    show_implants = models.BooleanField(default=False)
    show_skill_queue = models.BooleanField(default=False)
    show_standings = models.BooleanField(default=False)
    show_wallet = models.BooleanField(default=False)
    anon_key = models.CharField(max_length=16, blank=True, null=True, default='')

    def __unicode__(self):
        return self.character.name

# Magical hook so this gets called when a new user is created
def create_characterconfig(sender, instance, created, **kwargs):
    if created:
        CharacterConfig.objects.create(character=instance)

post_save.connect(create_characterconfig, sender=Character)

# Character details
class CharacterDetails(models.Model):
    character = models.OneToOneField(Character, unique=True, primary_key=True, related_name='details')

    wallet_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    
    cha_attribute = models.SmallIntegerField(default=0)
    int_attribute = models.SmallIntegerField(default=0)
    mem_attribute = models.SmallIntegerField(default=0)
    per_attribute = models.SmallIntegerField(default=0)
    wil_attribute = models.SmallIntegerField(default=0)
    cha_bonus = models.SmallIntegerField(default=0)
    int_bonus = models.SmallIntegerField(default=0)
    mem_bonus = models.SmallIntegerField(default=0)
    per_bonus = models.SmallIntegerField(default=0)
    wil_bonus = models.SmallIntegerField(default=0)
    
    clone_name = models.CharField(max_length=32, default='')
    clone_skill_points= models.IntegerField(default=0)
    
    security_status = models.DecimalField(max_digits=6, decimal_places=4, default=0)

    last_known_location = models.CharField(max_length=255, default='')
    ship_item = models.ForeignKey('Item', blank=True, null=True)
    ship_name = models.CharField(max_length=128, default='')

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
        remaining = total_seconds(self.end_time - now)
        remain_sp = remaining / 60.0 * self.skill.get_sp_per_minute(self.character)
        required_sp = self.skill.get_sp_at_level(self.to_level) - self.skill.get_sp_at_level(self.to_level - 1)

        return round(100 - (remain_sp / required_sp * 100), 1)

    def get_completed_sp(self, charskill, now=None):
        if now is None:
            now = datetime.datetime.utcnow()
        
        remaining = total_seconds(self.end_time - now)
        remain_sp = remaining / 60.0 * self.skill.get_sp_per_minute(self.character)
        required_sp = self.skill.get_sp_at_level(self.to_level) - self.skill.get_sp_at_level(self.to_level - 1)

        base_sp = self.skill.get_sp_at_level(charskill.level)
        current_sp = charskill.points

        return (required_sp - remain_sp) - (current_sp - base_sp)
    
    def get_roman_level(self):
        return ['', 'I', 'II', 'III', 'IV', 'V'][self.to_level]

    def get_remaining(self):
        remaining = total_seconds(self.end_time - datetime.datetime.utcnow())
        return int(remaining)

# Faction standings
class FactionStanding(models.Model):
    faction = models.ForeignKey('Faction')
    character = models.ForeignKey('character')

    standing = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        ordering = ('-standing',)

# Corporation standings
class CorporationStanding(models.Model):
    corporation = models.ForeignKey('Corporation')
    character = models.ForeignKey('character')

    standing = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        ordering = ('-standing',)

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
            if parts[1].startswith('Moon') and len(parts) == 3:
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
        return self.name

    class MPTTMeta:
        order_insertion_by = ['name']

# ---------------------------------------------------------------------------
# Item categories
class ItemCategory(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    
    def __unicode__(self):
        return self.name

# ---------------------------------------------------------------------------
# Item groups
class ItemGroup(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    category = models.ForeignKey(ItemCategory)
    
    def __unicode__(self):
        return self.name

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
    
    base_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
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
    description = models.TextField()
    primary_attribute = models.SmallIntegerField(choices=ATTRIBUTE_CHOICES)
    secondary_attribute = models.SmallIntegerField(choices=ATTRIBUTE_CHOICES)

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
# Wallet journal entries
class JournalEntry(models.Model):
    character = models.ForeignKey(Character)
    corp_wallet = models.ForeignKey(CorpWallet, null=True, blank=True)

    date = models.DateTimeField(db_index=True)

    ref_id = models.BigIntegerField()
    ref_type = models.ForeignKey('RefType')
    
    owner1_id = models.IntegerField()
    owner2_id = models.IntegerField()
    
    arg_name = models.CharField(max_length=128)
    arg_id = models.BigIntegerField()
    
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    balance = models.DecimalField(max_digits=17, decimal_places=2)
    reason = models.CharField(max_length=255)

    tax_corp = models.ForeignKey(Corporation, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ('-date',)

# ---------------------------------------------------------------------------
# Aggregated journal data
class JournalSummary(models.Model):
    character = models.ForeignKey(Character)
    corp_wallet = models.ForeignKey(CorpWallet, null=True, blank=True)

    year = models.IntegerField(default=0, db_index=True)
    month = models.IntegerField(default=0, db_index=True)
    day = models.IntegerField(default=0, db_index=True)

    ref_type = models.ForeignKey('RefType')

    total_in = models.DecimalField(max_digits=17, decimal_places=2)
    total_out = models.DecimalField(max_digits=17, decimal_places=2)
    balance = models.DecimalField(max_digits=17, decimal_places=2)

# ---------------------------------------------------------------------------
# Wallet transactions
class Transaction(models.Model):
    station = models.ForeignKey(Station)
    item = models.ForeignKey(Item)

    character = models.ForeignKey(Character)
    corp_wallet = models.ForeignKey(CorpWallet, null=True, blank=True)
    other_char = models.ForeignKey(SimpleCharacter, null=True, blank=True)
    other_corp = models.ForeignKey(Corporation, null=True, blank=True)

    transaction_id = models.BigIntegerField(db_index=True)
    date = models.DateTimeField(db_index=True)
    buy_transaction = models.BooleanField()
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=14, decimal_places=2)
    total_price = models.DecimalField(max_digits=17, decimal_places=2)

# ---------------------------------------------------------------------------
# RefTypes
class RefType(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)

    def __unicode__(self):
        return self.name

# ---------------------------------------------------------------------------
# Market orders
class MarketOrder(models.Model):
    order_id = models.BigIntegerField(primary_key=True)
    
    station = models.ForeignKey(Station)
    item = models.ForeignKey(Item)
    character = models.ForeignKey(Character)
    corp_wallet = models.ForeignKey(CorpWallet, null=True, blank=True)
    
    creator_character_id = models.IntegerField(db_index=True)

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
# Inventory flags
FLAG_NICE = {
    'HiSlot': ('High Slot', 0),
    'MedSlot': ('Mid Slot', 1),
    'LoSlot': ('Low Slot', 2),
    'RigSlot': ('Rig Slot', 3),
    'DroneBay': ('Drone Bay', 4),
    'ShipHangar': ('Ship Hangar', 5),
    'SpecializedFuelBay': ('Fuel Bay', 6),
}

class InventoryFlag(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    text = models.CharField(max_length=128)

    def nice_name(self):
        for pre, data in FLAG_NICE.items():
            if self.name.startswith(pre):
                return data[0]
        
        return self.name

    def sort_order(self):
        for pre, data in FLAG_NICE.items():
            if self.name.startswith(pre):
                return data[1]
        
        return 999

# ---------------------------------------------------------------------------
# Assets
class Asset(models.Model):
    asset_id = models.BigIntegerField()
    parent = models.BigIntegerField(blank=True, null=True)

    character = models.ForeignKey(Character, blank=True, null=True)
    corporation_id = models.IntegerField(blank=True, null=True)
    system = models.ForeignKey(System, blank=True, null=True)
    station = models.ForeignKey(Station, blank=True, null=True)

    item = models.ForeignKey(Item)
    name = models.CharField(max_length=128, blank=True, null=True)
    inv_flag = models.ForeignKey(InventoryFlag)
    quantity = models.IntegerField()
    raw_quantity = models.IntegerField()
    singleton = models.BooleanField()

    def system_or_station(self):
        if self.station is not None:
            return self.station.name
        elif self.system is not None:
            return self.system.name
        else:
            return None

#    def __unicode__(self):
#        return '%s' % (self.name)

# ---------------------------------------------------------------------------
# Contracts
class Contract(models.Model):
    contract_id = models.IntegerField(db_index=True)

    issuer_char = models.ForeignKey(SimpleCharacter, related_name="contract_issuers")
    issuer_corp = models.ForeignKey(Corporation, related_name="contract_issuers")
    assignee_id = models.IntegerField(blank=True, null=True)
    acceptor_id = models.IntegerField(blank=True, null=True)

    start_station = models.ForeignKey(Station, blank=True, null=True, related_name="contract_starts")
    end_station = models.ForeignKey(Station, blank=True, null=True, related_name="contract_ends")

    type = models.CharField(max_length=16)
    status = models.CharField(max_length=24)
    title = models.CharField(max_length=64)
    for_corp = models.BooleanField()
    public = models.BooleanField()

    date_issued = models.DateTimeField()
    date_expired = models.DateTimeField()
    date_accepted = models.DateTimeField(blank=True, null=True)
    date_completed = models.DateTimeField(blank=True, null=True)
    num_days = models.IntegerField()

    price = models.DecimalField(max_digits=15, decimal_places=2)
    reward = models.DecimalField(max_digits=15, decimal_places=2)
    collateral = models.DecimalField(max_digits=15, decimal_places=2)
    buyout = models.DecimalField(max_digits=15, decimal_places=2)
    volume = models.DecimalField(max_digits=16, decimal_places=4)

    retrieved_items = models.BooleanField(default=False)

    def __unicode__(self):
        if self.type == 'Courier':
            return '#%d (%s, %s -> %s)' % (self.contract_id, self.type, self.start_station.short_name, self.end_station.short_name)
        else:
            return '#%d (%s, %s)' % (self.contract_id, self.type, self.start_station.short_name)

    class Meta:
        ordering = ('-date_issued',)
    
    def get_issuer_name(self):
        if self.for_corp:
            return self.issuer_corp.name
        else:
            return self.issuer_char.name

# Contract items
class ContractItem(models.Model):
    contract_id = models.IntegerField(db_index=True)
    item = models.ForeignKey(Item, related_name='contract_items')

    quantity = models.IntegerField()
    raw_quantity = models.IntegerField()
    singleton = models.BooleanField()
    included = models.BooleanField()

# ---------------------------------------------------------------------------
# Skill plan storage disaster
class SkillPlan(models.Model):
    PRIVATE_VISIBILITY = 1
    PUBLIC_VISIBILITY = 2
    GLOBAL_VISIBILITY = 3
    VISIBILITY_CHOICES = (
        (PRIVATE_VISIBILITY, 'Private'),
        (PUBLIC_VISIBILITY, 'Public'),
        (GLOBAL_VISIBILITY, 'Global'),
    )

    user = models.ForeignKey(User)

    name = models.CharField(max_length=64)
    visibility = models.IntegerField(default=1, choices=VISIBILITY_CHOICES)

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return '%s - %s' % (self.user.username, self.name)

class SPEntry(models.Model):
    skill_plan = models.ForeignKey(SkillPlan, related_name='entries')

    position = models.IntegerField()

    sp_remap = models.ForeignKey('SPRemap', blank=True, null=True)
    sp_skill = models.ForeignKey('SPSkill', blank=True, null=True)

    class Meta:
        ordering = ('position',)

    def __unicode__(self):
        if self.sp_remap is None:
            return str(self.sp_skill)
        else:
            return str(self.sp_remap)

class SPRemap(models.Model):
    int_stat = models.IntegerField()
    mem_stat = models.IntegerField()
    per_stat = models.IntegerField()
    wil_stat = models.IntegerField()
    cha_stat = models.IntegerField()

    def __unicode__(self):
        return 'Int: %d, Mem: %d, Per: %d, Wil: %d, Cha: %d' % (self.int_stat, self.mem_stat,
            self.per_stat, self.wil_stat, self.cha_stat)

class SPSkill(models.Model):
    skill = models.ForeignKey(Skill)
    level = models.IntegerField()
    priority = models.IntegerField()

    def __unicode__(self):
        return '%s, level %d, priority %d' % (self.skill.item.name, self.level, self.priority)

# ---------------------------------------------------------------------------
# Industry jobs
class IndustryJob(models.Model):
    FAILED_STATUS = 0
    DELIVERED_STATUS = 1
    ABORTED_STATUS = 2
    GM_ABORTED_STATUS = 3
    INFLIGHT_UNANCHORED_STATUS = 4
    DESTROYED_STATUS = 5
    STATUS_CHOICES = (
        (FAILED_STATUS, 'Failed'),
        (DELIVERED_STATUS, 'Delivered'),
        (ABORTED_STATUS, 'Aborted'),
        (GM_ABORTED_STATUS, 'GM aborted'),
        (INFLIGHT_UNANCHORED_STATUS, 'Inflight unanchored'),
        (DESTROYED_STATUS, 'Destroyed'),
    )

    NONE_ACTIVITY = 0
    MANUFACTURING_ACTIVITY = 1
    RESEARCHING_TECHNOLOGY_ACTIVITY = 2
    RESEARCHING_TIME_ACTIVITY = 3
    RESEARCHING_MATERIAL_ACTIVITY = 4
    COPYING_ACTIVITY = 5
    DUPLICATING_ACTIVITY = 6
    REVERSE_ENGINEERING_ACTIVITY = 7
    INVENTION_ACTIVITY = 8
    ACTIVITY_CHOICES = (
        (NONE_ACTIVITY, 'None'),
        (MANUFACTURING_ACTIVITY, 'Manufacturing'),
        (RESEARCHING_TECHNOLOGY_ACTIVITY, 'Researching Technology'),
        (RESEARCHING_TIME_ACTIVITY, 'PE Research'),
        (RESEARCHING_MATERIAL_ACTIVITY, 'ME Research'),
        (COPYING_ACTIVITY, 'Copying'),
        (DUPLICATING_ACTIVITY, 'Duplicating'),
        (REVERSE_ENGINEERING_ACTIVITY, 'Reverse Engineering'),
        (INVENTION_ACTIVITY, 'Invention'),
    )

    character = models.ForeignKey(Character)
    corporation = models.ForeignKey(Corporation, blank=True, null=True)

    job_id = models.IntegerField()
    assembly_line_id = models.IntegerField()
    container_id = models.BigIntegerField()
    location_id = models.BigIntegerField()

    # asset ID?
    #item_id = models.IntegerField()
    item_productivity_level = models.IntegerField()
    item_material_level = models.IntegerField()

    output_location_id = models.BigIntegerField()
    installer_id = models.IntegerField()
    runs = models.IntegerField()
    licensed_production_runs_remaining = models.IntegerField()
    licensed_production_runs = models.IntegerField()

    system = models.ForeignKey(System)
    container_location_id = models.IntegerField()
    
    material_multiplier = models.DecimalField(max_digits=5, decimal_places=3)
    character_material_multiplier = models.DecimalField(max_digits=5, decimal_places=3)
    time_multiplier = models.DecimalField(max_digits=5, decimal_places=3)
    character_time_multiplier = models.DecimalField(max_digits=5, decimal_places=3)

    installed_item = models.ForeignKey(Item, related_name='job_installed_items')
    installed_flag = models.ForeignKey(InventoryFlag, related_name='job_installed_flags')
    output_item = models.ForeignKey(Item, related_name='job_output_items')
    output_flag = models.ForeignKey(InventoryFlag, related_name='job_output_flags')

    completed = models.IntegerField()
    completed_status = models.IntegerField(choices=STATUS_CHOICES)
    activity = models.IntegerField(choices=ACTIVITY_CHOICES)
   
    install_time = models.DateTimeField()
    begin_time = models.DateTimeField()
    end_time = models.DateTimeField()
    pause_time = models.DateTimeField()
    
    class Meta:
        ordering = ('-end_time',)

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

    def __unicode__(self):
        return '%dx %s' % (self.count, self.item.name)

# ---------------------------------------------------------------------------
# Blueprint instances - an owned blueprint
class BlueprintInstance(models.Model):
    user = models.ForeignKey(User, blank=True, null=True)
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
        PES = 5 #fixme: self.character.production_efficiency_skill
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

# ---------------------------------------------------------------------------
