from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, OTPChallenge


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'phone_number', 'balance', 'points', 'is_platform_admin']
    fieldsets = UserAdmin.fieldsets + (
        ('Finances', {'fields': ('phone_number', 'balance', 'points')}),
        ('Roles et securite', {'fields': ('is_platform_admin', 'otp_enabled', 'sponsor')}),
    )


admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(OTPChallenge)
class OTPChallengeAdmin(admin.ModelAdmin):
    list_display = ['user', 'purpose', 'expires_at', 'used_at', 'attempts', 'created_at']
    list_filter = ['purpose', 'used_at']
    search_fields = ['user__username', 'user__email', 'user__phone_number']
    readonly_fields = ['code_hash', 'created_at']
