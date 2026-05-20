from django.contrib import admin

from .models import Investment, InvestmentTier, SupportTicket, Transaction


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


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('subject', 'user', 'status', 'priority', 'created_at', 'updated_at')
    list_filter = ('status', 'priority')
    search_fields = ('subject', 'message', 'user__username', 'user__phone_number')
