### University Project: Facial Attendance & Check-In Engine

---

# SmartRoll: AI-Powered Facial Recognition Attendance System

**SmartRoll** is a full-featured, asynchronous web application designed to automate classroom attendance. By leveraging a powerful stack including Django, Celery, and Redis, this system offloads heavy AI processing to background workers, ensuring a fast and responsive user experience. It identifies students from a single photograph and provides a complete, interactive attendance report.

---

## Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [How It Works](#how-it-works)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Screenshots](#screenshots)
- [License](#license)

---

##  Features

- **Asynchronous Task Processing:** Utilizes **Celery** and **Redis** to offload slow face-encoding tasks to a background worker, ensuring the web interface remains fast and responsive at all times.
- **Dynamic Student Management:** Enroll new students, view the current roster, and delete students directly from the web interface.
- **Interactive Web UI:** A clean and easy-to-use interface built with Django for all functionalities.
- **AI-Powered Recognition:** Leverages a pre-trained deep learning model via the `face_recognition` library for robust identification.
- **Instant Visual Feedback:** Displays the processed classroom photo with recognized faces highlighted in labeled boxes.
- **Database Integration:** Uses a robust SQLite database to manage student records.

---

##  System Architecture

This project uses a modern, decoupled architecture to handle long-running tasks without blocking the user interface.



1.  **Django Web Server:** The user-facing component that handles fast HTTP requests, serves web pages, and saves initial data.
2.  **Redis:** A high-speed message broker. When a slow task is needed (like re-encoding faces), Django places a "job ticket" into Redis.
3.  **Celery Worker:** A separate background process that constantly monitors Redis. When it sees a new job ticket, it picks it up and executes the slow, CPU-intensive AI task, leaving the web server free to handle other users.

---

##  How It Works

### Enrollment (Managed via Web UI)
- An instructor navigates to the "Add Student" page and submits the form.
- The Django backend instantly saves the student's info to the database and sends a "rebuild encodings" job to **Redis**.
- A **Celery worker** picks up this job in the background and runs the slow process of re-scanning the `dataset` and creating the new `encodings.pickle` file, all without making the user wait.

### Recognition (Daily Use via Web App)
- The instructor uploads a classroom photo.
- The Django backend pulls the official student roster from the database.
- It detects all faces, computes their encodings, and compares them against the latest `encodings.pickle` database.
- The results are rendered directly on the webpage for immediate review.

---

##  Technology Stack

- **Backend:** Python, Django
- **Asynchronous Task Queue:** Celery, Redis
- **Database:** SQLite
- **Computer Vision:** OpenCV
- **Facial Recognition:** `face_recognition` (dlib)
- **Frontend:** HTML, Tailwind CSS (via CDN)

---

## Getting Started

Follow these steps to get the project running on your local machine.

### Prerequisites

- Python 3.8+
- Homebrew (for macOS users, to install `cmake` and `redis`)

### Installation & Setup

1.  **Clone the repository:**
    ```sh
    git clone [https://github.com/Pranav188/SmartRoll.git](https://github.com/Pranav188/SmartRoll.git)
    cd SmartRoll
    ```

2.  **Create and activate a virtual environment:**
    ```sh
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Python libraries:**
    ```sh
    pip install opencv face_recognition
    ```

4.  **Install and run Redis:**
    ```sh
    brew install redis
    brew services start redis
    ```

5.  **Set up the Database:**
    ```sh
    python manage.py migrate
    ```

### Running the Application

To run the application, you need **two separate terminals**.

**In Terminal 1 - Start the Celery Worker:**
```sh
celery -A smart_roll worker -l info
```
---

## Screenshots
Here is a showcase of the SmartRoll application's user interface.
<br>

<p align="center">
  <strong>Main Attendance Page</strong><br>
  <em>A minimalist, simple UI for uploading a classroom photo.</em>
  <br>
  <img src="/screenshots/home.png" alt="Main Attendance Page" width="700">
</p>

<br>

### Student Management

A consistent and intuitive interface for managing the student roster.

|                                 Enroll New Student                                 |                                   View Roster                                   |
|:----------------------------------------------------------------------------------:|:-------------------------------------------------------------------------------:|
|                *A clean form for adding students and their photos.*                |              *A simple list to view and delete enrolled students.*              |
| <img src="/screenshots/add_student.png" alt="Enroll New Student Page" width="400"> | <img src="/screenshots/student_list.png" alt="Student Roster Page" width="400"> |

---
## License
This project is licensed under the MIT License.

MIT © Pranav