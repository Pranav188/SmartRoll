from django.urls import path
from . import views

urlpatterns = [
    path('', views.attendance_view, name='attendance'),
]