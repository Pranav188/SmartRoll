from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import FileSystemStorage
from .face_recognition_engine import process_attendance, rebuild_encodings
from .models import Student
import os
import shutil
from django.conf import settings


def attendance_view(request):
    context = {}
    if request.method == 'POST' and request.FILES.get('classroom_photo'):
        # Get the list of all students FROM THE DATABASE
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
            # Create student in database
            student, created = Student.objects.get_or_create(name=student_name)

            # Create a directory for the student's photos
            student_dir = os.path.join(settings.BASE_DIR, 'dataset', student_name)
            os.makedirs(student_dir, exist_ok=True)

            # Save the photos
            for photo in photos:
                fs = FileSystemStorage(location=student_dir)
                fs.save(photo.name, photo)

            # Trigger a rebuild of the encodings file
            rebuild_encodings()

            return redirect('student_list')

    return render(request, 'core/add_student.html')


def delete_student_view(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        # Delete student directory from dataset
        student_dir = os.path.join(settings.BASE_DIR, 'dataset', student.name)
        if os.path.exists(student_dir):
            shutil.rmtree(student_dir)

        # Delete student from database
        student.delete()

        # Trigger a rebuild of the encodings file
        rebuild_encodings()

        return redirect('student_list')
    # If not a POST request, redirect to the list view
    return redirect('student_list')


from .face_recognition_engine import process_attendance
import os

# Your master list of students. In a real app, this would come from a database.
ALL_STUDENTS = [
    "ashish", "keshav", "nikhil", "pranav", "rishiraj",
    "rushil", "saumya", "vedantd", "vedantr"
]

def attendance_view(request):
    context = {}
    if request.method == 'POST' and request.FILES.get('classroom_photo'):
        classroom_photo = request.FILES['classroom_photo']
        fs = FileSystemStorage()

        # Save the uploaded photo temporarily
        filename = fs.save(classroom_photo.name, classroom_photo)
        uploaded_file_path = fs.path(filename)

        # Process the image using our engine
        present, absent, output_image_url = process_attendance(uploaded_file_path, ALL_STUDENTS)

        context = {
            'present_students': present,
            'absent_students': absent,
            'processed_image_url': output_image_url,
            'present_count': len(present),
            'absent_count': len(absent)
        }

        # Clean up the original uploaded file that was temporarily saved
        os.remove(uploaded_file_path)

    return render(request, 'core/attendance.html', context)