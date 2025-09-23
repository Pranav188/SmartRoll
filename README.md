University Project Title: Facial-Attendance-&-CheckIn-Engine

# SmartRoll: AI-Powered Facial Recognition Attendance System

**SmartRoll** is a web application designed to automate classroom attendance. By leveraging the power of computer vision, this system identifies all known students from a single photograph of a classroom and instantly generates a complete, user-friendly attendance report. This project refactors a terminal-based script into a robust and interactive Django web app.

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [License](#license)

---

## Features

- **Interactive Web Interface:** An easy-to-use UI built with Django for uploading classroom photos and viewing results instantly.
- **Automated Attendance:** Mark attendance for an entire classroom in seconds.
- **AI-Powered Recognition:** Utilizes a powerful, pre-trained deep learning model via the `face_recognition` library for robust identification..
- **Visual Feedback:** Displays the processed classroom photo with recognized faces highlighted in labeled boxes.
- **Adjustable Accuracy:** The recognition tolerance can be easily configured to control false positives.

---

## How It Works?

The system operates in two main phases:

### Enrollment (One-Time Setup)
- The standalone script `encode_faces.py` scans the `dataset/` directory.
- For each student's image, a unique 128-point **facial encoding** is generated.
- All encodings are serialized and saved into the `encodings.pickle` file, which acts as the application's face database.

### Recognition (Daily Use via Web App)
- The instructor navigates to the SmartRoll web application in their browser.
- They upload a classroom photo using the simple web form.
- The Django backend receives the image, detects all faces, computes their encodings, and compares them against the `encodings.pickle` database.
- The results, including "Present" and "Absent" lists and the processed image, are rendered directly on the webpage for immediate review.


---

## Technology Stack

- **Backend:** Python, Django
- **Computer Vision:** OpenCV
- **Facial Recognition:** `face_recognition` (dlib)
- **Data Serialization:** Pickle
- **Frontend:** HTML, Tailwind CSS (via CDN)

---

## Getting Started

Follow these steps to get the project running on your local machine.

### Prerequisites

- Python 3.8+
- pip and venv (virtual environment)

### Installation

1. Clone the repository
   
   `git clone https://github.com/Pranav188/SmartRoll.git`
   
   `cd SmartRoll`

2. Create and activate a virtual environment
   
   `python3 -m venv .venv`
   
   `source .venv/bin/activate`


3. Install necessary libraries
   
   `pip3 install opencv-python face_recognition`

Note: If on macOS and face_recognition (dlib) install fails, install cmake first

`brew install cmake`

4. Enroll Students:
    - Create a unique folder inside `dataset/` for each student (e.g., `dataset/Vedant_Sitoot/`).
    - Add 1–2 clear, well-lit photos of each student to their respective folder.
    - Run the enrollment command:
      ```sh
      python encode_faces.py
      ```
5.  Run the Django Application:
    - First, apply the initial database migrations:
      ```sh
      python manage.py migrate
      ```
    - Then, start the development server:
      ```sh
      python manage.py runserver
      ```
    - Open your web browser and navigate to `http://127.0.0.1:8000/`.


## License

MIT © Pranav

