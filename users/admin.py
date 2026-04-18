from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'phone_number', 'balance', 'points', 'is_platform_admin']
    # Add custom fields to standard admin form
    fieldsets = UserAdmin.fieldsets + (
        ('Finances & Gamification', {'fields': ('phone_number', 'balance', 'points')}),
        ('Rôles et Parrainage', {'fields': ('is_platform_admin', 'sponsor', 'binary_position')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
