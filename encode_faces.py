import face_recognition
import pickle
import cv2
import os


dataset_path = "dataset"
print("[INFO] Starting to process faces...")


known_encodings = [] # store feature vectors, which are facial features represented by numbers
known_names = [] # store person name


for person_name in os.listdir(dataset_path):
    person_path = os.path.join(dataset_path, person_name)

    # skip non-directory files
    if not os.path.isdir(person_path):
        continue

    print(f"[INFO] Processing images for {person_name}...")

    # loop over each image for the current person
    for image_name in os.listdir(person_path):
        image_path = os.path.join(person_path, image_name)

        # read the image and convert it from BGR (OpenCV default) to RGB
        image = cv2.imread(image_path)
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # detect the face boxes. We assume one face per image for enrollment.
        # hog is a facial detection model, alterative is CNN (hog is faster than CNN)
        # hog == histogram of oriented gradients
        boxes = face_recognition.face_locations(rgb_image, model='hog')

        # compute the facial embedding for the face
        encodings = face_recognition.face_encodings(rgb_image, boxes)

        # loop over the encodings and add them to our lists
        for encoding in encodings:
            known_encodings.append(encoding)
            known_names.append(person_name)

# save the encodings and names to a file using pickle
print("[INFO] Serializing encodings...")
data = {"encodings": known_encodings, "names": known_names}
with open("encodings.pickle", "wb") as f:
    f.write(pickle.dumps(data))

print("[INFO] Encodings saved successfully to 'encodings.pickle'")