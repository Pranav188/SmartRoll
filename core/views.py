from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
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