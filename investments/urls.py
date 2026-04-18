from django.urls import path
from . import views
from . import admin_views

urlpatterns = [
    # Routes Utilisateur standard
    path('', views.home, name='home'),
    path('trade/', views.trade, name='trade'),
    path('api/simulate/', views.simulate_investment_api, name='simulate_investment_api'),
    path('booster/', views.booster, name='booster'),
    path('withdraw/', views.withdraw_request, name='withdraw_request'),
    path('profile/', views.profile, name='profile'),
    
    # Paramètres du Profil
    path('profile/password/', views.settings_password, name='settings_password'),
    path('profile/theme/', views.settings_theme, name='settings_theme'),
    path('profile/points/', views.settings_points, name='settings_points'),
    path('profile/info/', views.settings_info, name='settings_info'),
    path('profile/history/', views.settings_history, name='settings_history'),
    path('profile/support/', views.settings_support, name='settings_support'),
    
    # Notifications Globables
    path('notifications/', views.notifications_list, name='notifications'),
    path('api/notifications/unread-count/', views.unread_notifications_count, name='api_unread_notifications_count'),
    
    # Panels d'Administration Customisés
    path('manager/', admin_views.manager_dashboard, name='manager_dashboard'),
    path('manager/tx/<int:tx_id>/<str:action>/', admin_views.process_transaction, name='process_transaction'),
    
    path('superadmin/', admin_views.superadmin_dashboard, name='superadmin_dashboard'),
    path('superadmin/settings/', admin_views.admin_settings_view, name='admin_settings'),
    path('superadmin/mobile-money/', admin_views.admin_payment_config_view, name='admin_payment_config'),
    
    # Nouvelles Vues CRUD Sur-Mesure
    path('superadmin/users/', admin_views.admin_users_view, name='admin_users'),
    path('superadmin/users/create/', admin_views.admin_user_create_view, name='admin_user_create'),
    path('superadmin/users/<int:user_id>/edit/', admin_views.admin_user_edit_view, name='admin_user_edit'),
    path('superadmin/users/<int:user_id>/delete/', admin_views.admin_user_delete_view, name='admin_user_delete'),
    path('superadmin/users/<int:user_id>/toggle/', admin_views.admin_user_toggle, name='admin_user_toggle'),
    path('superadmin/transactions/', admin_views.admin_transactions_view, name='admin_transactions'),
    path('superadmin/products/', admin_views.admin_products_view, name='admin_products'),
    path('superadmin/products/<int:prod_id>/toggle/', admin_views.admin_product_toggle, name='admin_product_toggle'),
]
