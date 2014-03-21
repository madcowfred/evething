from django.contrib import admin
from thing.models import APIKey, BlueprintInstance, Campaign, Character, CharacterConfig, Corporation, \
    Alliance, APIKeyFailure, Asset, AssetSummary, BlueprintComponent, Blueprint

class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'key_type', 'valid')

class BlueprintInstanceAdmin(admin.ModelAdmin):
    list_display = ('blueprint', 'original', 'material_level', 'productivity_level')

class CharacterAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Character information', {
            'fields': ['name', 'corporation']
        }),
    ]
    
    list_display = ('id', 'name', 'corporation')

class CampaignAdmin(admin.ModelAdmin):
    prepopulated_fields = { 'slug': ( 'title', ) }

class AllianceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'short_name')

class APIKeyFailureAdmin(admin.ModelAdmin):
    list_display = ('user', 'keyid', 'fail_time')

class AssetAdmin(admin.ModelAdmin):
    list_display = ('character', 'system', 'station', 'item', 'quantity')

class AssetSummaryAdmin(admin.ModelAdmin):
    list_display = ('character', 'system', 'station', 'total_items', 'total_value')

class BlueprintComponentAdmin(admin.ModelAdmin):
    list_display = ('blueprint', 'item', 'count', 'needs_waste')

class BlueprintAdmin(admin.ModelAdmin):
    list_display = ('name', 'item', 'production_time')


admin.site.register(APIKey, APIKeyAdmin)
admin.site.register(Character, CharacterAdmin)
admin.site.register(CharacterConfig)
admin.site.register(BlueprintInstance, BlueprintInstanceAdmin)
admin.site.register(Campaign, CampaignAdmin)
admin.site.register(Corporation)
admin.site.register(Alliance, AllianceAdmin)
admin.site.register(APIKeyFailure, APIKeyFailureAdmin)
admin.site.register(Asset, AssetAdmin)
admin.site.register(AssetSummary, AssetSummaryAdmin)
admin.site.register(BlueprintComponent, BlueprintComponentAdmin)
admin.site.register(Blueprint, BlueprintAdmin)
