from django.urls import path

from . import views

urlpatterns = [
    path('', views.MainViews.as_view(), name="main"),
    path('delete_wagon/<int:pk>/', views.DeleteWagonView.as_view(), name='delete_wagon'),
    path('delete_event/<int:pk>/', views.DeleteEventView.as_view(), name="delete_event"),
    path('export/event/<int:pk>/', views.ExportEventView.as_view(), name="export_event"),
    path('export/period/', views.ExportPeriodView.as_view(), name="export_period"),
    path('references/', views.ReferencesView.as_view(), name="references"),
]
