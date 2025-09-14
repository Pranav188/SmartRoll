import face_recognition
import pickle
import cv2
from datetime import datetime
import os


ALL_STUDENTS = [
    #insert student names here
]
CLASSROOM_IMAGE_PATH = "classroom.jpg"


ENCODINGS_PATH = "encodings.pickle"
DETECTION_MODEL = 'hog'
OUTPUT_CSV_PATH = f"attendance_{datetime.now().strftime('%Y-%m-%d')}.csv"

# 1. Load the known faces and embeddings
print("[INFO] Loading encodings...")
with open(ENCODINGS_PATH, "rb") as f:
    data = pickle.load(f)

# 2. Load the classroom image
print(f"[INFO] Processing classroom image: {CLASSROOM_IMAGE_PATH}")
image = cv2.imread(CLASSROOM_IMAGE_PATH)
if image is None:
    print(f"[ERROR] Could not load image from {CLASSROOM_IMAGE_PATH}.")
    exit()
rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) # covert from BGR to RGB

# 3. Detect faces
print("[INFO] Detecting faces in the image...")
boxes = face_recognition.face_locations(rgb_image, model=DETECTION_MODEL)
encodings = face_recognition.face_encodings(rgb_image, boxes)
print(f"[INFO] Found {len(boxes)} face(s) in the image.")

# 4. Identify the students present
present_students = set()
for encoding in encodings:
    # Compare faces with a stricter tolerance. Lower is stricter. 0.6 is default.
    matches = face_recognition.compare_faces(data["encodings"], encoding, tolerance=0.5)

    name = "Unknown"

    if True in matches:
        matched_idxs = [i for (i, b) in enumerate(matches) if b]
        counts = {}
        for i in matched_idxs:
            name = data["names"][i]
            counts[name] = counts.get(name, 0) + 1
        name = max(counts, key=counts.get)

    # Only add the student to the present list if a confident match was found
    if name != "Unknown":
        present_students.add(name)

# 5. Determine who is absent
all_students_set = set(ALL_STUDENTS)
absent_students = all_students_set.difference(present_students)

# 6. Print and save the report
print("\n--- FINAL ATTENDANCE REPORT ---")
print("\n[PRESENT]")
if present_students:
    for student in sorted(list(present_students)):
        print(f"  - {student}")
else:
    print("  No students were recognized as present.")

print("\n[ABSENT]")
if absent_students:
    for student in sorted(list(absent_students)):
        print(f"  - {student}")
else:
    print("All students are present.")

# Save the report to a CSV file
print(f"\n[INFO] Saving attendance report to {OUTPUT_CSV_PATH}...")
with open(OUTPUT_CSV_PATH, 'w') as f:
    f.writelines("Name,Status,Timestamp\n")
    timestamp = datetime.now().strftime('%H:%M:%S')
    for student in sorted(ALL_STUDENTS):
        status = "Present" if student in present_students else "Absent"
        f.writelines(f"{student},{status},{timestamp}\n")

print("[INFO] Process complete.")