from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from .models import Student
from .face_recognition_engine import process_attendance, rebuild_encodings_task  # <-- Import the task
import os
import shutil


def attendance_view(request):
    context = {}
    if request.method == 'POST' and request.FILES.get('classroom_photo'):
        # Get the list of all students directly FROM THE DATABASE
        all_students = list(Student.objects.values_list('name', flat=True))

        classroom_photo = request.FILES['classroom_photo']
        fs = FileSystemStorage()
        filename = fs.save(classroom_photo.name, classroom_photo)
        uploaded_file_path = fs.path(filename)

        present, absent, output_image_url = process_attendance(uploaded_file_path, all_students)

        context = {
            'present_students': present,
            'absent_students': absent,
            'processed_image_url': output_image_url,
            'present_count': len(present),
            'absent_count': len(absent)
        }
        os.remove(uploaded_file_path)

    return render(request, 'core/attendance.html', context)


def student_list_view(request):
    students = Student.objects.all().order_by('name')
    return render(request, 'core/student_list.html', {'students': students})


def add_student_view(request):
    if request.method == 'POST':
        student_name = request.POST.get('student_name')
        photos = request.FILES.getlist('photos')

        if student_name and photos:
            student, created = Student.objects.get_or_create(name=student_name)

            student_dir = os.path.join(settings.BASE_DIR, 'dataset', student_name)
            os.makedirs(student_dir, exist_ok=True)

            for photo in photos:
                fs = FileSystemStorage(location=student_dir)
                fs.save(photo.name, photo)

            # --- CHANGE ---
            # Instead of running the slow function directly,
            # we tell our Celery worker to run it in the background.
            print("[INFO] Sending rebuild_encodings task to Celery worker...")
            rebuild_encodings_task.delay()

            return redirect('student_list')

    return render(request, 'core/add_student.html')


def delete_student_view(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        student_dir = os.path.join(settings.BASE_DIR, 'dataset', student.name)
        if os.path.exists(student_dir):
            shutil.rmtree(student_dir)

        student.delete()

        # --- CHANGE ---
        # Trigger the background task here as well.
        print("[INFO] Sending rebuild_encodings task to Celery worker...")
        rebuild_encodings_task.delay()

        return redirect('student_list')

    return redirect('student_list')