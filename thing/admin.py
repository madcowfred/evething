from django.contrib import admin
from thing.models import APIKey, BlueprintInstance, Campaign, Character, CharacterConfig, Corporation, \
    Alliance, APIKeyFailure, Asset, AssetSummary, BlueprintComponent, Blueprint, CorpWallet, \
    TaskState, CharacterDetails, Contract, UserProfile, Transaction, JournalEntry, Colony, Pin, BlueprintProduct, \
    IndustryJob, SkillPlan


class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'key_type', 'corporation', 'valid')
    raw_id_fields = ('characters', 'corp_character', 'corporation')
    search_fields = ['characters__name', 'corporation__name']


class BlueprintInstanceAdmin(admin.ModelAdmin):
    list_display = ('blueprint', 'original', 'material_level', 'productivity_level')


class CharacterAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Character information', {
            'fields': ['name', 'corporation']
        }),
    ]
    list_display = ('id', 'name', 'corporation')
    raw_id_fields = ('corporation',)
    search_fields = ['name']


class CharacterDetailsAdmin(admin.ModelAdmin):
    raw_id_fields = ('character',)


class CharacterConfigAdmin(admin.ModelAdmin):
    raw_id_fields = ('character',)


class CampaignAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}


class AllianceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'short_name')


class APIKeyFailureAdmin(admin.ModelAdmin):
    list_display = ('user', 'keyid', 'fail_time')


class AssetAdmin(admin.ModelAdmin):
    list_display = ('character', 'system', 'station', 'item', 'quantity')
    raw_id_fields = ('character',)


class AssetSummaryAdmin(admin.ModelAdmin):
    list_display = ('character', 'system', 'station', 'total_items', 'total_value')
    raw_id_fields = ('character',)


class BlueprintComponentAdmin(admin.ModelAdmin):
    list_display = ('blueprint', 'activity', 'item', 'count', 'consumed')
    list_filter = ('activity',)


class BlueprintProductAdmin(admin.ModelAdmin):
    list_display = ('blueprint', 'activity', 'item', 'count')
    list_filter = ('activity',)


class BlueprintAdmin(admin.ModelAdmin):
    list_display = ('name',)


class CorpWalletAdmin(admin.ModelAdmin):
    list_display = ('corporation', 'description', 'balance')
    raw_id_fields = ('corporation',)


class TaskStateAdmin(admin.ModelAdmin):
    list_display = ('keyid', 'url', 'state', 'mod_time', 'next_time', 'parameter')


class ContractAdmin(admin.ModelAdmin):
    list_display = ('contract_id', 'date_issued', 'date_expired', 'date_completed')
    raw_id_fields = ('character', 'corporation', 'issuer_char', 'issuer_corp')


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_seen', 'can_add_keys')


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'date', 'character', 'corp_wallet', 'other_char', 'other_corp', 'item')


class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'character', 'corp_wallet', 'ref_type', 'amount', 'owner1_id', 'owner2_id', 'reason')
    raw_id_fields = ('character', 'corp_wallet', 'tax_corp')


class ColonyAdmin(admin.ModelAdmin):
    list_display = ('character', 'system', 'planet', 'planet_type', 'last_update', 'level', 'pins')
    list_filter = ('level', 'planet_type')
    raw_id_fields = ('character',)


class PinAdmin(admin.ModelAdmin):
    list_display = ('pin_id', 'colony', 'type', 'expires')


class IndustryJobAdmin(admin.ModelAdmin):
    list_display = ('character', 'activity', 'blueprint', 'product', 'status')
    list_filter = ('activity', 'status')
    raw_id_fields = ('character', 'corporation')

class SkillPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'visibility')
    list_filter = ('visibility',)

admin.site.register(APIKey, APIKeyAdmin)
admin.site.register(Character, CharacterAdmin)
admin.site.register(CharacterConfig, CharacterConfigAdmin)
admin.site.register(BlueprintInstance, BlueprintInstanceAdmin)
admin.site.register(Campaign, CampaignAdmin)
admin.site.register(Corporation)
admin.site.register(Alliance, AllianceAdmin)
admin.site.register(APIKeyFailure, APIKeyFailureAdmin)
admin.site.register(Asset, AssetAdmin)
admin.site.register(AssetSummary, AssetSummaryAdmin)
admin.site.register(BlueprintComponent, BlueprintComponentAdmin)
admin.site.register(BlueprintProduct, BlueprintProductAdmin)
admin.site.register(Blueprint, BlueprintAdmin)
admin.site.register(CorpWallet, CorpWalletAdmin)
admin.site.register(TaskState, TaskStateAdmin)
admin.site.register(CharacterDetails, CharacterDetailsAdmin)
admin.site.register(Contract, ContractAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(JournalEntry, JournalEntryAdmin)
admin.site.register(Colony, ColonyAdmin)
admin.site.register(Pin, PinAdmin)
admin.site.register(IndustryJob, IndustryJobAdmin)
admin.site.register(SkillPlan, SkillPlanAdmin)
