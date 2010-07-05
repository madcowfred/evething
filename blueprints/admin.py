from everdi.blueprints.models import BlueprintInstance, Character
from django.contrib import admin

class CharacterAdmin(admin.ModelAdmin):
	fieldsets = [
		(None, {'fields': ['user']}),
		('Character information', {'fields': ['name', 'api_key', 'industry_skill', 'production_efficiency_skill']}),
		('Factory costs', {'fields': ['factory_cost', 'factory_per_hour']}),
		('Taxes', {'fields': ['sales_tax', 'brokers_fee']}),
	]

admin.site.register(Character, CharacterAdmin)
admin.site.register(BlueprintInstance)
