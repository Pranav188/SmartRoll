import face_recognition
import pickle
import cv2
import os
from django.conf import settings

# --- Configuration ---
ENCODINGS_FILE = os.path.join(settings.BASE_DIR, 'encodings.pickle')
DATASET_PATH = os.path.join(settings.BASE_DIR, 'dataset')
DETECTION_MODEL = 'hog'
MATCH_TOLERANCE = 0.5


def process_attendance(image_path, all_students):
    """
    Takes an uploaded image, processes it, and returns attendance results.
    """
    try:
        with open(ENCODINGS_FILE, "rb") as f:
            data = pickle.load(f)
    except FileNotFoundError:
        return [], all_students, None

    image = cv2.imread(image_path)
    if image is None:
        return [], all_students, None

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb_image, model=DETECTION_MODEL)
    encodings = face_recognition.face_encodings(rgb_image, boxes)

    present_names = set()
    recognized_names_for_boxes = []

    for encoding in encodings:
        matches = face_recognition.compare_faces(data["encodings"], encoding, tolerance=MATCH_TOLERANCE)
        name = "Unknown"
        if True in matches:
            matched_idxs = [i for (i, b) in enumerate(matches) if b]
            counts = {}
            for i in matched_idxs:
                name = data["names"][i]
                counts[name] = counts.get(name, 0) + 1
            name = max(counts, key=counts.get)
            present_names.add(name)
        recognized_names_for_boxes.append(name)

    all_students_set = set(all_students)
    absent_names = all_students_set.difference(present_names)

    for (top, right, bottom, left), name in zip(boxes, recognized_names_for_boxes):
        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        cv2.rectangle(image, (left, top), (right, bottom), color, 2)
        y = top - 15 if top - 15 > 15 else top + 15
        cv2.putText(image, name, (left, y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)

    output_filename = "processed_" + os.path.basename(image_path)
    output_path = os.path.join(settings.MEDIA_ROOT, output_filename)
    cv2.imwrite(output_path, image)

    output_url = os.path.join(settings.MEDIA_URL, output_filename)

    return sorted(list(present_names)), sorted(list(absent_names)), output_url


def rebuild_encodings():
    """
    Scans the dataset directory, re-encodes all faces, and saves them.
    This function replaces the standalone encode_faces.py script.
    """
    print("[INFO] Rebuilding face encodings...")
    known_encodings = []
    known_names = []

    if not os.path.exists(DATASET_PATH):
        print("[WARNING] Dataset directory not found, skipping encoding.")
        return False

    student_names = [name for name in os.listdir(DATASET_PATH) if os.path.isdir(os.path.join(DATASET_PATH, name))]

    for person_name in student_names:
        person_path = os.path.join(DATASET_PATH, person_name)
        image_files = [f for f in os.listdir(person_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.heic'))]

        for image_name in image_files:
            image_path = os.path.join(person_path, image_name)
            image = cv2.imread(image_path)
            if image is None: continue

            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            boxes = face_recognition.face_locations(rgb_image, model=DETECTION_MODEL)

            if len(boxes) != 1: continue

            encodings = face_recognition.face_encodings(rgb_image, boxes)
            for encoding in encodings:
                known_encodings.append(encoding)
                known_names.append(person_name)

    print(f"[INFO] Found {len(known_encodings)} faces. Saving to pickle file.")
    data = {"encodings": known_encodings, "names": known_names}
    with open(ENCODINGS_FILE, "wb") as f:
        f.write(pickle.dumps(data))

    print("[INFO] Encodings rebuilt successfully.")
    return True

