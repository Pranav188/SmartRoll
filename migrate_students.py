import os
import django

# --- Setup Django Environment ---
# This is a special setup to allow this script to use your Django models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_roll.settings')
django.setup()
# --- End of Setup ---

from core.models import Student

def migrate():
    """
    Reads the dataset folder and creates Student entries in the database.
    """
    dataset_path = 'dataset'
    print("Starting migration...")

    if not os.path.exists(dataset_path):
        print(f"Error: Dataset directory '{dataset_path}' not found.")
        return

    # Get student names from the folder names
    student_folders = [name for name in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, name))]

    if not student_folders:
        print("No student folders found in the dataset directory.")
        return

    created_count = 0
    for student_name in student_folders:
        # get_or_create() is a safe way to add data.
        # It creates the student only if they don't already exist.
        student, created = Student.objects.get_or_create(name=student_name)
        if created:
            print(f"- Created database entry for: {student.name}")
            created_count += 1
        else:
            print(f"- Student '{student.name}' already exists in the database. Skipping.")

    print(f"\nMigration complete. Added {created_count} new students to the database.")

if __name__ == "__main__":
    migrate()