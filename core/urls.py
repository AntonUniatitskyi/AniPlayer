"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from myanime import views
from django.contrib.auth.views import LoginView, LogoutView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.AnimeTitleListView.as_view(), name="home"),
    path('anime/<slug:slug>/', views.AnimeTitleDetailView.as_view(), name='anime_detail'),
    path('login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
    # path('api/track-history/', views.track_history, name='track_history'),
    path('api/search/', views.search_anime_api, name='search_api'),
    path('api/update-status/', views.update_status, name='update_status'),
    path('profile/library/', views.UserLibraryView.as_view(), name='library'),
    path('api/save-progress/', views.save_progress, name='save_progress')
]
