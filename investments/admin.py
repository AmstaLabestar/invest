from django.contrib import admin
from .models import Investment, Transaction, Booster, UserBooster, InvestmentTier

@admin.register(InvestmentTier)
class InvestmentTierAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'badge', 'min_amount', 'daily_rate', 'cycle_days', 'is_active')
    list_filter = ('is_active',)
    ordering = ('level',)



@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'tier', 'amount_invested', 'status', 'start_date')
    list_filter = ('status', 'tier')
    search_fields = ('user__username', 'user__phone_number')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'tx_type', 'amount', 'status', 'provider', 'created_at')
    list_filter = ('status', 'tx_type', 'provider')
    search_fields = ('user__username', 'tx_reference')

@admin.register(Booster)
class BoosterAdmin(admin.ModelAdmin):
    list_display = ('name', 'multiplier', 'price', 'duration_days', 'is_active')

@admin.register(UserBooster)
class UserBoosterAdmin(admin.ModelAdmin):
    list_display = ('user', 'booster', 'start_date', 'end_date', 'is_active')
