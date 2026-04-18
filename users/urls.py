from django.urls import path
from .views import custom_login, custom_register, custom_logout

urlpatterns = [
    path('login/', custom_login, name='login'),
    path('register/', custom_register, name='register'),
    path('logout/', custom_logout, name='logout'),
]
