import face_recognition
import pickle
import os
import cv2
import numpy as np

# --- CONFIGURATION ---
ENCODINGS_PATH = "encodings.pickle"
DATASET_DIR = "dataset"
TOLERANCE = 0.5


def adjust_brightness(image, factor):
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * factor, 0, 255)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


def add_noise(image):
    row, col, ch = image.shape
    mean = 0
    var = 50
    sigma = var ** 0.5
    gauss = np.random.normal(mean, sigma, (row, col, ch))
    noisy = image + gauss
    return np.clip(noisy, 0, 255).astype(np.uint8)


def blur_image(image):
    return cv2.GaussianBlur(image, (5, 5), 0)


def stress_test():
    print(f"Loading Brain from {ENCODINGS_PATH}...")
    try:
        with open(ENCODINGS_PATH, "rb") as f:
            data = pickle.load(f)
    except FileNotFoundError:
        print("Error: encodings.pickle not found.")
        return

    known_encodings = data["encodings"]
    known_names = data["names"]

    total_tests = 0
    passed_tests = 0

    print(f"\n{'Test Case':<40} | {'Predicted':<15} | {'Result':<10}")
    print("-" * 70)

    # UPDATED: Walk through all subdirectories
    for root, dirs, files in os.walk(DATASET_DIR):
        for filename in files:
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue

            # Get the folder name as the "True Name" (e.g., dataset/pranav/image.jpg -> pranav)
            # We handle the case where the image might be in root or subfolder
            if root == DATASET_DIR:
                true_name = filename.split('.')[0].lower()
            else:
                true_name = os.path.basename(root).lower()

            # Load original
            path = os.path.join(root, filename)
            original_bgr = cv2.imread(path)
            if original_bgr is None: continue
            original_rgb = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2RGB)

            # Create 4 variants
            variants = [
                ("Original", original_rgb),
                ("Low Light", adjust_brightness(original_rgb, 0.5)),
                ("Overexposed", adjust_brightness(original_rgb, 1.5)),
                ("Motion Blur", blur_image(original_rgb)),
                ("Noise", add_noise(original_rgb))
            ]

            for variant_name, image in variants:
                total_tests += 1
                test_desc = f"{true_name} ({variant_name})"

                # Detect & Recognize
                boxes = face_recognition.face_locations(image, model="hog")
                encodings = face_recognition.face_encodings(image, boxes)

                prediction = "Unknown"

                if len(encodings) > 0:
                    # Compare to known DB
                    matches = face_recognition.compare_faces(known_encodings, encodings[0], tolerance=TOLERANCE)
                    dists = face_recognition.face_distance(known_encodings, encodings[0])

                    if True in matches:
                        best_match_index = np.argmin(dists)
                        prediction = known_names[best_match_index]

                # Check result
                # We check if the predicted name matches the folder name
                is_correct = prediction.lower() == true_name.lower()

                if is_correct:
                    passed_tests += 1
                    status = "PASS"
                else:
                    status = "FAIL"

                print(f"{test_desc:<40} | {prediction:<15} | {status}")

    if total_tests == 0:
        print("\nNo images found in dataset/ folder or subfolders.")
        return

    accuracy = (passed_tests / total_tests) * 100
    print("-" * 70)
    print(f"STRESS TEST RESULTS:")
    print(f"Total Scenarios: {total_tests}")
    print(f"Passed:          {passed_tests}")
    print(f"Robustness:      {accuracy:.2f}%")
    print("-" * 70)


if __name__ == "__main__":
    stress_test()