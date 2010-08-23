from django.contrib import admin
from everdi.rdi.models import BlueprintInstance, Character, Corporation, Timeframe

class CharacterAdmin(admin.ModelAdmin):
	fieldsets = [
		(None, {'fields': ['user']}),
		('Character information', {
			'fields': ['name', 'corporation', 'industry_skill', 'production_efficiency_skill']
		}),
		('Factory costs', {
			'fields': ['factory_cost', 'factory_per_hour']
		}),
		('Taxes', {
			'fields': ['sales_tax', 'brokers_fee']
		}),
		('API information', {
			'classes': ('collapse',),
			'fields': ['eve_user_id', 'eve_api_key', 'eve_character_id']
		}),
	]

class TimeframeAdmin(admin.ModelAdmin):
	prepopulated_fields = { 'slug': ( 'title', ) }

admin.site.register(Character, CharacterAdmin)
admin.site.register(BlueprintInstance)
admin.site.register(Corporation)
admin.site.register(Timeframe, TimeframeAdmin)
