from django.urls import path
from .views import custom_login, custom_logout, custom_register, otp_verify, settings_security

urlpatterns = [
    path('login/', custom_login, name='login'),
    path('login/otp/', otp_verify, name='otp_verify'),
    path('register/', custom_register, name='register'),
    path('profile/security/', settings_security, name='settings_security'),
    path('logout/', custom_logout, name='logout'),
]
