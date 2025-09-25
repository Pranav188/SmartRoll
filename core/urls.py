from django.urls import path
from . import views

urlpatterns = [
    path('', views.attendance_view, name='attendance'),
    path('students/', views.student_list_view, name='student_list'),
    path('students/add/', views.add_student_view, name='add_student'),
    path('students/<int:student_id>/delete/', views.delete_student_view, name='delete_student'),
]

