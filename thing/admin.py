from django.contrib import admin
from thing.models import APIKey, BlueprintInstance, Campaign, Character, CharacterConfig, Corporation

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

admin.site.register(APIKey, APIKeyAdmin)
admin.site.register(Character, CharacterAdmin)
admin.site.register(CharacterConfig)
admin.site.register(BlueprintInstance, BlueprintInstanceAdmin)
admin.site.register(Campaign, CampaignAdmin)
#admin.site.register(Corporation)
