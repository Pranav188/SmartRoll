import face_recognition
import pickle
import cv2
import os


dataset_path = "dataset"
encodings_file = 'encodings.pickle'
detection_model = 'hog'

def encode_faces():
    print("[INFO] Starting to process faces...")


    known_encodings = [] # store feature vectors, which are facial features represented by numbers
    known_names = [] # store person name
    total_images_scanned = 0
    total_faces_encoded = 0

    student_names = [name for name in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, name))]

    for person_name in student_names:
        person_path = os.path.join(dataset_path, person_name)

        image_files = [f for f in os.listdir(person_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not image_files:
            print(f"[WARNING] No images found for {person_name}. Skipping.")
            continue

        print(f"[INFO] Processing {len(image_files)} image(s) for {person_name}...")


        # loop over each image for the current person
        for image_name in image_files:
            image_path = os.path.join(person_path, image_name)
            total_images_scanned += 1

            # read the image and convert it from BGR (OpenCV default) to RGB
            image = cv2.imread(image_path)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # detect the face boxes. We assume one face per image for enrollment.
            # hog is a facial detection model, alterative is CNN (hog is faster than CNN)
            # hog == histogram of oriented gradients
            boxes = face_recognition.face_locations(rgb_image, model='hog')

            # skip images which contain more than one person (in /dataset)
            if len(boxes) != 1:
                print(f"[WARNING] Image {image_path} contains more than one face, skipping {image_name}")
            # compute the facial embedding for the face
            encodings = face_recognition.face_encodings(rgb_image, boxes)

            # loop over the encodings and add them to our lists
            for encoding in encodings:
                known_encodings.append(encoding)
                known_names.append(person_name)
                total_faces_encoded += 1


    # save the encodings and names to a file using pickle
    print("[INFO] Serializing encodings...")
    data = {"encodings": known_encodings, "names": known_names}
    with open("encodings.pickle", "wb") as f:
        f.write(pickle.dumps(data))

    print("[INFO] Encodings saved successfully to 'encodings.pickle'")

    # report (in terminal)
    print("\n" + "=" * 30)
    print(" ENROLLMENT SUMMARY")
    print("=" * 30)
    print(f"Total students: {len(student_names)}")
    print(f"Total images scanned: {total_images_scanned}")
    print(f"Total faces successfully encoded: {total_faces_encoded}")
    print(f"Encodings saved to '{encodings_file}'")
    print("=" * 30)