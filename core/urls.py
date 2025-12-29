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
from django.contrib.auth import views as auth_views
from django.conf.urls.static import static
from django.conf import settings
from django.views.generic import TemplateView
from myanime.forms import TelegramPasswordResetForm

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
    path('api/save-progress/', views.save_progress, name='save_progress'),
    path('settings/', views.settings_view, name='settings'),
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             form_class=TelegramPasswordResetForm
         ),
         name='password_reset'),

    # 2. Сообщение "Письмо отправлено"
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
         name='password_reset_done'),

    # 3. Ссылка из письма (ввод нового пароля)
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
         name='password_reset_confirm'),

    # 4. Успешно изменено
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
         name='password_reset_complete'),
    path('password-change/',
         auth_views.PasswordChangeView.as_view(
             template_name='registration/password_change_form.html',
             success_url='/settings/'  # После успеха вернемся в настройки
         ),
         name='password_change'),
    path('connect-telegram/', views.start_telegram_auth, name='connect_telegram'),
    path('connect-telegram/done/<str:token>/<str:chat_id>/', views.finish_telegram_auth, name='finish_telegram_auth'),
    path('api/subscribe/', views.toggle_subscription, name='toggle_subscription'),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript'), name='sw.js'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
