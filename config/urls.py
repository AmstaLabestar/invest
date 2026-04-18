from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')), # Authentification
    path('', include('investments.urls')), # Routes principales (Dashboard, Trade)
]
