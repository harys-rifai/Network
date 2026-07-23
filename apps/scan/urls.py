from django.urls import path
from . import views

urlpatterns = [
    path('', views.scan_list, name='scan_list'),
    path('add/', views.scan_trigger, name='scan_trigger'),
    path('<int:pk>/', views.scan_detail, name='scan_detail'),
    path('<int:pk>/edit/', views.scan_edit, name='scan_edit'),
    path('<int:pk>/delete/', views.scan_delete, name='scan_delete'),
]
