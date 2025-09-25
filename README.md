# University Project: Facial-Attendance-&-CheckIn-Engine

# SmartRoll: AI-Powered Facial Recognition Attendance System

**SmartRoll** is a full-featured web application designed to automate classroom attendance. By leveraging the power of computer vision and a Django backend, this system identifies students from a single photograph and provides a complete, interactive attendance report. Users can also manage the student roster directly through the web interface, including adding, viewing, and deleting students on the fly.

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [License](#license)

---

## Features

- **Dynamic Student Management:** Enroll new students, view the current roster, and delete students directly from the web interface without touching the command line.
- **Interactive Web UI:** A clean and easy-to-use interface built with Django for all functionalities.
- **Automated Attendance:** Mark attendance for an entire classroom in seconds from a single image upload.
- **AI-Powered Recognition:** Utilizes a powerful, pre-trained deep learning model via the `face_recognition` library for robust identification.
- **Instant Visual Feedback:** Displays the processed classroom photo with recognized faces highlighted in labeled boxes.
- **Database Integration:** Uses a robust SQLite database to manage student records, making the application a single source of truth.

---

## How It Works

The system operates in two main phases, both now managed through the web application:

### Enrollment (Managed via Web UI)
- An instructor navigates to the "Add Student" page.
- They enter the student's name and upload one or more clear photos through the web form.
- The Django backend automatically:
    1.  Creates a new student record in the **SQLite database**.
    2.  Saves the new photos to the `dataset/` directory.
    3.  Triggers a background process to re-scan the entire `dataset` and rebuild the `encodings.pickle` file, making the new student immediately recognizable.

### Recognition (Daily Use via Web App)
- The instructor navigates to the main attendance page and uploads a classroom photo.
- The Django backend pulls the official student roster from the database.
- It detects all faces in the photo, computes their encodings, and compares them against the `encodings.pickle` database.
- The results, including "Present" and "Absent" lists and the processed image, are rendered directly on the webpage for immediate review.

---

## Technology Stack

- **Backend:** Python, Django
- **Database:** SQLite
- **Computer Vision:** OpenCV
- **Facial Recognition:** `face_recognition` (dlib)
- **Data Serialization:** Pickle
- **Frontend:** HTML, Tailwind CSS (via CDN)

---

## Getting Started

Follow these steps to get the project running on your local machine.

### Prerequisites

- Python 3.8+
- `pip` and `venv` (virtual environment)

### Installation & Setup

1.  **Clone the repository:**
    ```sh
    git clone [https://github.com/Pranav188/SmartRoll.git](https://github.com/Pranav188/SmartRoll.git)
    cd SmartRoll
    ```

2.  **Create and activate a virtual environment:**
    ```sh
    # For macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    
    # For Windows
    python -m venv .venv
    .\.venv\Scripts\activate
    ```

3.  **Install necessary libraries:**
    ```sh
    pip install -r requirements.txt
    ```
    > **Note for macOS users:** If `dlib` installation fails, you may need to install `cmake` first: `brew install cmake`

4.  **Set up the Database:**
    - Run the initial database migrations to create your tables:
      ```sh
      python manage.py migrate
      ```

5.  **Run the Django Application:**
    - Start the development server:
      ```sh
      python manage.py runserver
      ```
    - Open your web browser and navigate to `http://127.0.0.1:8000/`.

### Usage

1.  From the main page, click **"Add Student"** to enroll your first few students using the web form.
2.  Click **"View Current Students"** to see the list of enrolled students.
3.  Once students are enrolled, return to the main page to upload a classroom photo and mark attendance.
4.  (Optional) For bulk enrollment, you can still manually place photos in the `dataset/` folder and run `python encode_faces.py`, but you must also add the students through the "Add Student" interface for the database to be aware of them.

---

## License

This project is licensed under the MIT License.
MIT © Pranav