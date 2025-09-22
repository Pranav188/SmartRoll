import face_recognition
import pickle
import cv2
import os
from django.conf import settings

# --- Configuration ---
# Construct the full path to the encodings file relative to the project's base directory
ENCODINGS_FILE = os.path.join(settings.BASE_DIR, 'encodings.pickle')
DETECTION_MODEL = 'hog'
MATCH_TOLERANCE = 0.5


def process_attendance(image_path, all_students):
    """
    Takes the path to an uploaded image, processes it using the facial recognition
    logic, and returns the lists of present/absent students and the path to a
    new image with faces highlighted.
    """
    # Load the known faces and embeddings
    try:
        with open(ENCODINGS_FILE, "rb") as f:
            data = pickle.load(f)
    except FileNotFoundError:
        # If the encodings file is missing, return empty results
        return [], all_students, None

    # Load the uploaded image
    image = cv2.imread(image_path)
    if image is None:
        return [], all_students, None

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Find all the faces and face encodings in the current frame of video
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

    # --- Draw boxes on the image and save it for display on the webpage ---
    for (top, right, bottom, left), name in zip(boxes, recognized_names_for_boxes):
        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        # Draw the box
        cv2.rectangle(image, (left, top), (right, bottom), color, 2)
        # Draw the label
        y = top - 15 if top - 15 > 15 else top + 15
        cv2.putText(image, name, (left, y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)

    # Save the output image to the media directory so it can be displayed on the web
    output_filename = "processed_" + os.path.basename(image_path)
    output_path = os.path.join(settings.MEDIA_ROOT, output_filename)
    cv2.imwrite(output_path, image)

    # Create a URL for the processed image
    output_url = os.path.join(settings.MEDIA_URL, output_filename)

    return sorted(list(present_names)), sorted(list(absent_names)), output_url


