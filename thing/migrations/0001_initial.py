# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'UserProfile'
        db.create_table('thing_userprofile', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['auth.User'], unique=True)),
            ('theme', self.gf('django.db.models.fields.CharField')(default='theme-default', max_length=32)),
            ('home_chars_per_row', self.gf('django.db.models.fields.IntegerField')(default=4)),
        ))
        db.send_create_signal('thing', ['UserProfile'])

        # Adding model 'APIKey'
        db.create_table('thing_apikey', (
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('vcode', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('access_mask', self.gf('django.db.models.fields.BigIntegerField')(null=True, blank=True)),
            ('key_type', self.gf('django.db.models.fields.CharField')(max_length=16, null=True, blank=True)),
            ('expires', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('valid', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('corp_character', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='corporate_apikey', null=True, to=orm['thing.Character'])),
            ('paid_until', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('thing', ['APIKey'])

        # Adding model 'APICache'
        db.create_table('thing_apicache', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('url', self.gf('django.db.models.fields.URLField')(max_length=200)),
            ('parameters', self.gf('django.db.models.fields.TextField')()),
            ('cached_until', self.gf('django.db.models.fields.DateTimeField')()),
            ('text', self.gf('django.db.models.fields.TextField')()),
            ('completed_ok', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('thing', ['APICache'])

        # Adding model 'Event'
        db.create_table('thing_event', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('issued', self.gf('django.db.models.fields.DateTimeField')()),
            ('text', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('thing', ['Event'])

        # Adding model 'Corporation'
        db.create_table('thing_corporation', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('ticker', self.gf('django.db.models.fields.CharField')(max_length=5, null=True, blank=True)),
            ('division1', self.gf('django.db.models.fields.CharField')(max_length=64, null=True, blank=True)),
            ('division2', self.gf('django.db.models.fields.CharField')(max_length=64, null=True, blank=True)),
            ('division3', self.gf('django.db.models.fields.CharField')(max_length=64, null=True, blank=True)),
            ('division4', self.gf('django.db.models.fields.CharField')(max_length=64, null=True, blank=True)),
            ('division5', self.gf('django.db.models.fields.CharField')(max_length=64, null=True, blank=True)),
            ('division6', self.gf('django.db.models.fields.CharField')(max_length=64, null=True, blank=True)),
            ('division7', self.gf('django.db.models.fields.CharField')(max_length=64, null=True, blank=True)),
        ))
        db.send_create_signal('thing', ['Corporation'])

        # Adding model 'CorpWallet'
        db.create_table('thing_corpwallet', (
            ('account_id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('corporation', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Corporation'])),
            ('account_key', self.gf('django.db.models.fields.IntegerField')()),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('balance', self.gf('django.db.models.fields.DecimalField')(max_digits=18, decimal_places=2)),
        ))
        db.send_create_signal('thing', ['CorpWallet'])

        # Adding model 'Character'
        db.create_table('thing_character', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('apikey', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.APIKey'], null=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('corporation', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Corporation'])),
            ('wallet_balance', self.gf('django.db.models.fields.DecimalField')(default=0.0, max_digits=18, decimal_places=2)),
            ('cha_attribute', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('int_attribute', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('mem_attribute', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('per_attribute', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('wil_attribute', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('cha_bonus', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('int_bonus', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('mem_bonus', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('per_bonus', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('wil_bonus', self.gf('django.db.models.fields.SmallIntegerField')(default=0)),
            ('clone_name', self.gf('django.db.models.fields.CharField')(default='', max_length=32)),
            ('clone_skill_points', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('factory_cost', self.gf('django.db.models.fields.DecimalField')(default=0.0, max_digits=8, decimal_places=2)),
            ('factory_per_hour', self.gf('django.db.models.fields.DecimalField')(default=0.0, max_digits=8, decimal_places=2)),
            ('sales_tax', self.gf('django.db.models.fields.DecimalField')(default=1.5, max_digits=3, decimal_places=2)),
            ('brokers_fee', self.gf('django.db.models.fields.DecimalField')(default=1.0, max_digits=3, decimal_places=2)),
        ))
        db.send_create_signal('thing', ['Character'])

        # Adding model 'CharacterConfig'
        db.create_table('thing_characterconfig', (
            ('character', self.gf('django.db.models.fields.related.OneToOneField')(related_name='config', unique=True, primary_key=True, to=orm['thing.Character'])),
            ('is_public', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('show_clone', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('show_implants', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('show_skill_queue', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('show_wallet', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('anon_key', self.gf('django.db.models.fields.CharField')(max_length=16, null=True, blank=True)),
        ))
        db.send_create_signal('thing', ['CharacterConfig'])

        # Adding model 'CharacterSkill'
        db.create_table('thing_characterskill', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('character', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Character'])),
            ('skill', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Skill'])),
            ('level', self.gf('django.db.models.fields.SmallIntegerField')()),
            ('points', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal('thing', ['CharacterSkill'])

        # Adding model 'SkillQueue'
        db.create_table('thing_skillqueue', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('character', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Character'])),
            ('skill', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Skill'])),
            ('start_time', self.gf('django.db.models.fields.DateTimeField')()),
            ('end_time', self.gf('django.db.models.fields.DateTimeField')()),
            ('start_sp', self.gf('django.db.models.fields.IntegerField')()),
            ('end_sp', self.gf('django.db.models.fields.IntegerField')()),
            ('to_level', self.gf('django.db.models.fields.SmallIntegerField')()),
        ))
        db.send_create_signal('thing', ['SkillQueue'])

        # Adding model 'Region'
        db.create_table('thing_region', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('thing', ['Region'])

        # Adding model 'Constellation'
        db.create_table('thing_constellation', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('region', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Region'])),
        ))
        db.send_create_signal('thing', ['Constellation'])

        # Adding model 'System'
        db.create_table('thing_system', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('constellation', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Constellation'])),
        ))
        db.send_create_signal('thing', ['System'])

        # Adding model 'Station'
        db.create_table('thing_station', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('short_name', self.gf('django.db.models.fields.CharField')(max_length=64, null=True, blank=True)),
            ('system', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.System'])),
        ))
        db.send_create_signal('thing', ['Station'])

        # Adding model 'MarketGroup'
        db.create_table('thing_marketgroup', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('parent', self.gf('mptt.fields.TreeForeignKey')(blank=True, related_name='children', null=True, to=orm['thing.MarketGroup'])),
            ('lft', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('rght', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('tree_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('level', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
        ))
        db.send_create_signal('thing', ['MarketGroup'])

        # Adding model 'ItemCategory'
        db.create_table('thing_itemcategory', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('thing', ['ItemCategory'])

        # Adding model 'ItemGroup'
        db.create_table('thing_itemgroup', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('category', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.ItemCategory'])),
        ))
        db.send_create_signal('thing', ['ItemGroup'])

        # Adding model 'Item'
        db.create_table('thing_item', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('item_group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.ItemGroup'])),
            ('market_group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.MarketGroup'], null=True, blank=True)),
            ('portion_size', self.gf('django.db.models.fields.IntegerField')()),
            ('volume', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=16, decimal_places=4)),
            ('sell_price', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=15, decimal_places=2)),
            ('buy_price', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=15, decimal_places=2)),
        ))
        db.send_create_signal('thing', ['Item'])

        # Adding model 'Skill'
        db.create_table('thing_skill', (
            ('item', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['thing.Item'], unique=True, primary_key=True)),
            ('rank', self.gf('django.db.models.fields.SmallIntegerField')()),
            ('primary_attribute', self.gf('django.db.models.fields.SmallIntegerField')()),
            ('secondary_attribute', self.gf('django.db.models.fields.SmallIntegerField')()),
        ))
        db.send_create_signal('thing', ['Skill'])

        # Adding model 'PriceHistory'
        db.create_table('thing_pricehistory', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('region', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Region'])),
            ('item', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Item'])),
            ('date', self.gf('django.db.models.fields.DateField')()),
            ('minimum', self.gf('django.db.models.fields.DecimalField')(max_digits=18, decimal_places=2)),
            ('maximum', self.gf('django.db.models.fields.DecimalField')(max_digits=18, decimal_places=2)),
            ('average', self.gf('django.db.models.fields.DecimalField')(max_digits=18, decimal_places=2)),
            ('movement', self.gf('django.db.models.fields.BigIntegerField')()),
            ('orders', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal('thing', ['PriceHistory'])

        # Adding unique constraint on 'PriceHistory', fields ['region', 'item', 'date']
        db.create_unique('thing_pricehistory', ['region_id', 'item_id', 'date'])

        # Adding model 'Campaign'
        db.create_table('thing_campaign', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('slug', self.gf('django.db.models.fields.SlugField')(max_length=32)),
            ('start_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('end_date', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal('thing', ['Campaign'])

        # Adding M2M table for field corp_wallets on 'Campaign'
        db.create_table('thing_campaign_corp_wallets', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('campaign', models.ForeignKey(orm['thing.campaign'], null=False)),
            ('corpwallet', models.ForeignKey(orm['thing.corpwallet'], null=False))
        ))
        db.create_unique('thing_campaign_corp_wallets', ['campaign_id', 'corpwallet_id'])

        # Adding M2M table for field characters on 'Campaign'
        db.create_table('thing_campaign_characters', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('campaign', models.ForeignKey(orm['thing.campaign'], null=False)),
            ('character', models.ForeignKey(orm['thing.character'], null=False))
        ))
        db.create_unique('thing_campaign_characters', ['campaign_id', 'character_id'])

        # Adding model 'Transaction'
        db.create_table('thing_transaction', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('station', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Station'])),
            ('character', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Character'])),
            ('item', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Item'])),
            ('corp_wallet', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.CorpWallet'], null=True, blank=True)),
            ('transaction_id', self.gf('django.db.models.fields.BigIntegerField')()),
            ('date', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('buy_transaction', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('quantity', self.gf('django.db.models.fields.IntegerField')()),
            ('price', self.gf('django.db.models.fields.DecimalField')(max_digits=14, decimal_places=2)),
            ('total_price', self.gf('django.db.models.fields.DecimalField')(max_digits=17, decimal_places=2)),
        ))
        db.send_create_signal('thing', ['Transaction'])

        # Adding model 'MarketOrder'
        db.create_table('thing_marketorder', (
            ('order_id', self.gf('django.db.models.fields.BigIntegerField')(primary_key=True)),
            ('station', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Station'])),
            ('item', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Item'])),
            ('character', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Character'])),
            ('corp_wallet', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.CorpWallet'], null=True, blank=True)),
            ('escrow', self.gf('django.db.models.fields.DecimalField')(max_digits=14, decimal_places=2)),
            ('price', self.gf('django.db.models.fields.DecimalField')(max_digits=14, decimal_places=2)),
            ('total_price', self.gf('django.db.models.fields.DecimalField')(max_digits=17, decimal_places=2)),
            ('buy_order', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('volume_entered', self.gf('django.db.models.fields.IntegerField')()),
            ('volume_remaining', self.gf('django.db.models.fields.IntegerField')()),
            ('minimum_volume', self.gf('django.db.models.fields.IntegerField')()),
            ('issued', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('expires', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
        ))
        db.send_create_signal('thing', ['MarketOrder'])

        # Adding model 'InventoryFlag'
        db.create_table('thing_inventoryflag', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('text', self.gf('django.db.models.fields.CharField')(max_length=128)),
        ))
        db.send_create_signal('thing', ['InventoryFlag'])

        # Adding model 'Asset'
        db.create_table('thing_asset', (
            ('id', self.gf('django.db.models.fields.BigIntegerField')(primary_key=True)),
            ('parent', self.gf('mptt.fields.TreeForeignKey')(blank=True, related_name='children', null=True, to=orm['thing.Asset'])),
            ('character', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Character'], null=True, blank=True)),
            ('corporation', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Corporation'], null=True, blank=True)),
            ('system', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.System'], null=True, blank=True)),
            ('station', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Station'], null=True, blank=True)),
            ('item', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Item'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            ('inv_flag', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.InventoryFlag'])),
            ('quantity', self.gf('django.db.models.fields.IntegerField')()),
            ('raw_quantity', self.gf('django.db.models.fields.IntegerField')()),
            ('singleton', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('lft', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('rght', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('tree_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('level', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
        ))
        db.send_create_signal('thing', ['Asset'])

        # Adding model 'Blueprint'
        db.create_table('thing_blueprint', (
            ('id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('item', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Item'])),
            ('production_time', self.gf('django.db.models.fields.IntegerField')()),
            ('productivity_modifier', self.gf('django.db.models.fields.IntegerField')()),
            ('material_modifier', self.gf('django.db.models.fields.IntegerField')()),
            ('waste_factor', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal('thing', ['Blueprint'])

        # Adding model 'BlueprintComponent'
        db.create_table('thing_blueprintcomponent', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('blueprint', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Blueprint'])),
            ('item', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Item'])),
            ('count', self.gf('django.db.models.fields.IntegerField')()),
            ('needs_waste', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('thing', ['BlueprintComponent'])

        # Adding model 'BlueprintInstance'
        db.create_table('thing_blueprintinstance', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('blueprint', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['thing.Blueprint'])),
            ('original', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('material_level', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('productivity_level', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal('thing', ['BlueprintInstance'])


    def backwards(self, orm):
        # Removing unique constraint on 'PriceHistory', fields ['region', 'item', 'date']
        db.delete_unique('thing_pricehistory', ['region_id', 'item_id', 'date'])

        # Deleting model 'UserProfile'
        db.delete_table('thing_userprofile')

        # Deleting model 'APIKey'
        db.delete_table('thing_apikey')

        # Deleting model 'APICache'
        db.delete_table('thing_apicache')

        # Deleting model 'Event'
        db.delete_table('thing_event')

        # Deleting model 'Corporation'
        db.delete_table('thing_corporation')

        # Deleting model 'CorpWallet'
        db.delete_table('thing_corpwallet')

        # Deleting model 'Character'
        db.delete_table('thing_character')

        # Deleting model 'CharacterConfig'
        db.delete_table('thing_characterconfig')

        # Deleting model 'CharacterSkill'
        db.delete_table('thing_characterskill')

        # Deleting model 'SkillQueue'
        db.delete_table('thing_skillqueue')

        # Deleting model 'Region'
        db.delete_table('thing_region')

        # Deleting model 'Constellation'
        db.delete_table('thing_constellation')

        # Deleting model 'System'
        db.delete_table('thing_system')

        # Deleting model 'Station'
        db.delete_table('thing_station')

        # Deleting model 'MarketGroup'
        db.delete_table('thing_marketgroup')

        # Deleting model 'ItemCategory'
        db.delete_table('thing_itemcategory')

        # Deleting model 'ItemGroup'
        db.delete_table('thing_itemgroup')

        # Deleting model 'Item'
        db.delete_table('thing_item')

        # Deleting model 'Skill'
        db.delete_table('thing_skill')

        # Deleting model 'PriceHistory'
        db.delete_table('thing_pricehistory')

        # Deleting model 'Campaign'
        db.delete_table('thing_campaign')

        # Removing M2M table for field corp_wallets on 'Campaign'
        db.delete_table('thing_campaign_corp_wallets')

        # Removing M2M table for field characters on 'Campaign'
        db.delete_table('thing_campaign_characters')

        # Deleting model 'Transaction'
        db.delete_table('thing_transaction')

        # Deleting model 'MarketOrder'
        db.delete_table('thing_marketorder')

        # Deleting model 'InventoryFlag'
        db.delete_table('thing_inventoryflag')

        # Deleting model 'Asset'
        db.delete_table('thing_asset')

        # Deleting model 'Blueprint'
        db.delete_table('thing_blueprint')

        # Deleting model 'BlueprintComponent'
        db.delete_table('thing_blueprintcomponent')

        # Deleting model 'BlueprintInstance'
        db.delete_table('thing_blueprintinstance')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'thing.apicache': {
            'Meta': {'object_name': 'APICache'},
            'cached_until': ('django.db.models.fields.DateTimeField', [], {}),
            'completed_ok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'parameters': ('django.db.models.fields.TextField', [], {}),
            'text': ('django.db.models.fields.TextField', [], {}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200'})
        },
        'thing.apikey': {
            'Meta': {'ordering': "('id',)", 'object_name': 'APIKey'},
            'access_mask': ('django.db.models.fields.BigIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'corp_character': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'corporate_apikey'", 'null': 'True', 'to': "orm['thing.Character']"}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'key_type': ('django.db.models.fields.CharField', [], {'max_length': '16', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'paid_until': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'valid': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'vcode': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        'thing.asset': {
            'Meta': {'object_name': 'Asset'},
            'character': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Character']", 'null': 'True', 'blank': 'True'}),
            'corporation': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Corporation']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.BigIntegerField', [], {'primary_key': 'True'}),
            'inv_flag': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.InventoryFlag']"}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Item']"}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': "orm['thing.Asset']"}),
            'quantity': ('django.db.models.fields.IntegerField', [], {}),
            'raw_quantity': ('django.db.models.fields.IntegerField', [], {}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'singleton': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'station': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Station']", 'null': 'True', 'blank': 'True'}),
            'system': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.System']", 'null': 'True', 'blank': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        'thing.blueprint': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Blueprint'},
            'components': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'component_of'", 'symmetrical': 'False', 'through': "orm['thing.BlueprintComponent']", 'to': "orm['thing.Item']"}),
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Item']"}),
            'material_modifier': ('django.db.models.fields.IntegerField', [], {}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'production_time': ('django.db.models.fields.IntegerField', [], {}),
            'productivity_modifier': ('django.db.models.fields.IntegerField', [], {}),
            'waste_factor': ('django.db.models.fields.IntegerField', [], {})
        },
        'thing.blueprintcomponent': {
            'Meta': {'object_name': 'BlueprintComponent'},
            'blueprint': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Blueprint']"}),
            'count': ('django.db.models.fields.IntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Item']"}),
            'needs_waste': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'thing.blueprintinstance': {
            'Meta': {'ordering': "('blueprint',)", 'object_name': 'BlueprintInstance'},
            'blueprint': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Blueprint']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'material_level': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'original': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'productivity_level': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'thing.campaign': {
            'Meta': {'ordering': "('title',)", 'object_name': 'Campaign'},
            'characters': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['thing.Character']", 'null': 'True', 'blank': 'True'}),
            'corp_wallets': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['thing.CorpWallet']", 'null': 'True', 'blank': 'True'}),
            'end_date': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '32'}),
            'start_date': ('django.db.models.fields.DateTimeField', [], {}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'thing.character': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Character'},
            'apikey': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.APIKey']", 'null': 'True', 'blank': 'True'}),
            'brokers_fee': ('django.db.models.fields.DecimalField', [], {'default': '1.0', 'max_digits': '3', 'decimal_places': '2'}),
            'cha_attribute': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'cha_bonus': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'clone_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '32'}),
            'clone_skill_points': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'corporation': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Corporation']"}),
            'factory_cost': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '8', 'decimal_places': '2'}),
            'factory_per_hour': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '8', 'decimal_places': '2'}),
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'int_attribute': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'int_bonus': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'mem_attribute': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'mem_bonus': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'per_attribute': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'per_bonus': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'sales_tax': ('django.db.models.fields.DecimalField', [], {'default': '1.5', 'max_digits': '3', 'decimal_places': '2'}),
            'skill_queue': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'training_by'", 'symmetrical': 'False', 'through': "orm['thing.SkillQueue']", 'to': "orm['thing.Skill']"}),
            'skills': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'learned_by'", 'symmetrical': 'False', 'through': "orm['thing.CharacterSkill']", 'to': "orm['thing.Skill']"}),
            'wallet_balance': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '18', 'decimal_places': '2'}),
            'wil_attribute': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'wil_bonus': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'})
        },
        'thing.characterconfig': {
            'Meta': {'object_name': 'CharacterConfig'},
            'anon_key': ('django.db.models.fields.CharField', [], {'max_length': '16', 'null': 'True', 'blank': 'True'}),
            'character': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'config'", 'unique': 'True', 'primary_key': 'True', 'to': "orm['thing.Character']"}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'show_clone': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'show_implants': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'show_skill_queue': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'show_wallet': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'thing.characterskill': {
            'Meta': {'object_name': 'CharacterSkill'},
            'character': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Character']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.SmallIntegerField', [], {}),
            'points': ('django.db.models.fields.IntegerField', [], {}),
            'skill': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Skill']"})
        },
        'thing.constellation': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Constellation'},
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'region': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Region']"})
        },
        'thing.corporation': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Corporation'},
            'division1': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'division2': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'division3': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'division4': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'division5': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'division6': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'division7': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'ticker': ('django.db.models.fields.CharField', [], {'max_length': '5', 'null': 'True', 'blank': 'True'})
        },
        'thing.corpwallet': {
            'Meta': {'ordering': "('corporation', 'account_id')", 'object_name': 'CorpWallet'},
            'account_id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'account_key': ('django.db.models.fields.IntegerField', [], {}),
            'balance': ('django.db.models.fields.DecimalField', [], {'max_digits': '18', 'decimal_places': '2'}),
            'corporation': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Corporation']"}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        'thing.event': {
            'Meta': {'ordering': "('-issued', '-id')", 'object_name': 'Event'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'issued': ('django.db.models.fields.DateTimeField', [], {}),
            'text': ('django.db.models.fields.TextField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'thing.inventoryflag': {
            'Meta': {'object_name': 'InventoryFlag'},
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'text': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'thing.item': {
            'Meta': {'object_name': 'Item'},
            'buy_price': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '15', 'decimal_places': '2'}),
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'item_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.ItemGroup']"}),
            'market_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.MarketGroup']", 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'portion_size': ('django.db.models.fields.IntegerField', [], {}),
            'sell_price': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '15', 'decimal_places': '2'}),
            'volume': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '16', 'decimal_places': '4'})
        },
        'thing.itemcategory': {
            'Meta': {'object_name': 'ItemCategory'},
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        'thing.itemgroup': {
            'Meta': {'object_name': 'ItemGroup'},
            'category': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.ItemCategory']"}),
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        'thing.marketgroup': {
            'Meta': {'object_name': 'MarketGroup'},
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': "orm['thing.MarketGroup']"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        'thing.marketorder': {
            'Meta': {'ordering': "('buy_order', 'item__name')", 'object_name': 'MarketOrder'},
            'buy_order': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'character': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Character']"}),
            'corp_wallet': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.CorpWallet']", 'null': 'True', 'blank': 'True'}),
            'escrow': ('django.db.models.fields.DecimalField', [], {'max_digits': '14', 'decimal_places': '2'}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'issued': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Item']"}),
            'minimum_volume': ('django.db.models.fields.IntegerField', [], {}),
            'order_id': ('django.db.models.fields.BigIntegerField', [], {'primary_key': 'True'}),
            'price': ('django.db.models.fields.DecimalField', [], {'max_digits': '14', 'decimal_places': '2'}),
            'station': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Station']"}),
            'total_price': ('django.db.models.fields.DecimalField', [], {'max_digits': '17', 'decimal_places': '2'}),
            'volume_entered': ('django.db.models.fields.IntegerField', [], {}),
            'volume_remaining': ('django.db.models.fields.IntegerField', [], {})
        },
        'thing.pricehistory': {
            'Meta': {'ordering': "('-date',)", 'unique_together': "(('region', 'item', 'date'),)", 'object_name': 'PriceHistory'},
            'average': ('django.db.models.fields.DecimalField', [], {'max_digits': '18', 'decimal_places': '2'}),
            'date': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Item']"}),
            'maximum': ('django.db.models.fields.DecimalField', [], {'max_digits': '18', 'decimal_places': '2'}),
            'minimum': ('django.db.models.fields.DecimalField', [], {'max_digits': '18', 'decimal_places': '2'}),
            'movement': ('django.db.models.fields.BigIntegerField', [], {}),
            'orders': ('django.db.models.fields.IntegerField', [], {}),
            'region': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Region']"})
        },
        'thing.region': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Region'},
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        'thing.skill': {
            'Meta': {'object_name': 'Skill'},
            'item': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['thing.Item']", 'unique': 'True', 'primary_key': 'True'}),
            'primary_attribute': ('django.db.models.fields.SmallIntegerField', [], {}),
            'rank': ('django.db.models.fields.SmallIntegerField', [], {}),
            'secondary_attribute': ('django.db.models.fields.SmallIntegerField', [], {})
        },
        'thing.skillqueue': {
            'Meta': {'ordering': "('start_time',)", 'object_name': 'SkillQueue'},
            'character': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Character']"}),
            'end_sp': ('django.db.models.fields.IntegerField', [], {}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'skill': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Skill']"}),
            'start_sp': ('django.db.models.fields.IntegerField', [], {}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {}),
            'to_level': ('django.db.models.fields.SmallIntegerField', [], {})
        },
        'thing.station': {
            'Meta': {'object_name': 'Station'},
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'short_name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'system': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.System']"})
        },
        'thing.system': {
            'Meta': {'ordering': "('name',)", 'object_name': 'System'},
            'constellation': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Constellation']"}),
            'id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '32'})
        },
        'thing.transaction': {
            'Meta': {'object_name': 'Transaction'},
            'buy_transaction': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'character': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Character']"}),
            'corp_wallet': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.CorpWallet']", 'null': 'True', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Item']"}),
            'price': ('django.db.models.fields.DecimalField', [], {'max_digits': '14', 'decimal_places': '2'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {}),
            'station': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['thing.Station']"}),
            'total_price': ('django.db.models.fields.DecimalField', [], {'max_digits': '17', 'decimal_places': '2'}),
            'transaction_id': ('django.db.models.fields.BigIntegerField', [], {})
        },
        'thing.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            'home_chars_per_row': ('django.db.models.fields.IntegerField', [], {'default': '4'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'theme': ('django.db.models.fields.CharField', [], {'default': "'theme-default'", 'max_length': '32'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'})
        }
    }

    complete_apps = ['thing']