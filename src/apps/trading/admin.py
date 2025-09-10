from django.contrib import admin
from .models import TradingPackage, Investment, Trade, ProfitHistory

admin.site.register(TradingPackage)
admin.site.register(Investment)
admin.site.register(Trade)
admin.site.register(ProfitHistory)
