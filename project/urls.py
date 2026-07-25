from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from apps.dashboard import views as dashboard_views
from apps.scan import views as scan_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('apps.dashboard.urls')),
    path('scan/', include('apps.scan.urls')),
    path('trace-connection/', dashboard_views.trace_connection, name='trace_connection'),
    path('api/trace/<str:trace_id>/progress/', scan_views.trace_progress, name='trace_progress'),
    path('db-maintenance/', dashboard_views.db_maintenance, name='db_maintenance'),
]
