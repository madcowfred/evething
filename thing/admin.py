from django.contrib import admin
from evething.thing.models import APIKey, BlueprintInstance, Character, Corporation, Timeframe

class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('id', 'vcode', 'user', 'key_type', 'valid')

class BlueprintInstanceAdmin(admin.ModelAdmin):
    list_display = ('blueprint', 'bp_type', 'material_level', 'productivity_level')

class CharacterAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Character information', {
            'fields': ['name', 'corporation']
        }),
        ('Factory costs', {
            'fields': ['factory_cost', 'factory_per_hour']
        }),
        ('Taxes', {
            'fields': ['sales_tax', 'brokers_fee']
        }),
    ]
    
    list_display = ('name', 'corporation', 'apikey')

class TimeframeAdmin(admin.ModelAdmin):
    prepopulated_fields = { 'slug': ( 'title', ) }

admin.site.register(APIKey, APIKeyAdmin)
admin.site.register(Character, CharacterAdmin)
admin.site.register(BlueprintInstance, BlueprintInstanceAdmin)
admin.site.register(Corporation)
admin.site.register(Timeframe, TimeframeAdmin)
