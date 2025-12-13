### University Project: Facial Attendance & Check-In Engine

---

# SmartRoll: AI-Powered Facial Recognition Attendance System

**SmartRoll** is a production-grade, asynchronous web application designed to automate classroom attendance. It features a modern, containerized architecture that leverages Django, Celery, Redis, and PostgreSQL to handle heavy AI processing in the background, ensuring a seamless user experience even under load.

It identifies students from a single classroom photograph with 100% verified robustness against lighting and noise variations.

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

- **Asynchronous Architecture:** Decouples heavy face-encoding tasks using Celery and Redis, preventing server timeouts and keeping the UI responsive.
- **Production-Grade Database:** Migrated from SQLite to PostgreSQL to handle concurrent writes and ensure data integrity at scale.
- **Containerized Deployment:** Fully Dockerized stack (Web, Worker, DB, Redis) ensures consistent performance across local development and AWS cloud environments.
- **Robust AI Recognition:** Achieves 100% detection accuracy on stress-tested datasets (low-light, motion blur, and noise) using optimized OpenCV/dlib preprocessing.
- **Dynamic Student Management:** Full CRUD interface for enrolling students, viewing the roster, and managing the dataset directly via the web UI.
- **Instant Visual Feedback:** Renders bounding boxes and labels on processed images for immediate verification.

---

##  System Architecture

This project uses a decoupled, event-driven architecture to solve the "blocking request" problem common in AI web apps.



1.  **Django Web Server:** Handles HTTP requests and serves the frontend. It offloads CPU-intensive tasks to the message broker.
2.  **Redis:** Acts as a high-speed message broker and result backend, queuing tasks for the worker.
3.  **Celery Worker:** A dedicated background process that picks up encoding jobs, processes images using `face_recognition`, and updates the database.
4. **PostgreSQL:** The persistent relational database storing student records and metadata.
---

##  How It Works

### Enrollment (Async Flow)
- An instructor submits a new student photo via the "Add Student" page.
- Django saves the initial record to PostgreSQL and pushes a `rebuild_encodings` task to Redis.
- The Celery worker picks up the task, processes the `dataset` folder, and updates the `encodings.pickle` file in the background.

### Recognition (Real-Time)
- The instructor uploads a classroom photo.
- The system detects faces, computes 128-d embeddings, and compares them against the known encodings.
- Results are returned instantly, identifying present students and marking unknowns.


---

##  Technology Stack

- **Backend:** Python, Django
- **Database:** PostgreSQL (Migrated from SQLite)
- **Task Queue:** Celery, Redis
- **DevOps:** Docker, Docker Compose, AWS EC2
- **Computer Vision:** OpenCV, `face_recognition` (dlib)
- **Frontend:** HTML, Tailwind CSS

---

## Getting Started

The easiest way to run SmartRoll is using Docker. No manual installation of Python, Postgres, or Redis is required.

### Prerequisites

- [Docker Desktop](#https://www.docker.com/products/docker-desktop/)
- Git

### Installation & Setup

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/Pranav188/SmartRoll.git
    cd SmartRoll
    ```

2.  **Create the Environment File:** Create a file named .env in the root directory and add your configuration (or use the default for local dev):
    ```sh
    POSTGRES_DB=smartroll_db
    POSTGRES_USER=smartroll_user
    POSTGRES_PASSWORD=password123
    DATABASE_URL=postgres://smartroll_user:password123@db:5432/smartroll_db
    CELERY_BROKER_URL=redis://redis:6379/0
    CELERY_RESULT_BACKEND=redis://redis:6379/0
    SECRET_KEY=dev_secret_key
    DEBUG=True
    ALLOWED_HOSTS=.localhost,127.0.0.1,0.0.0.0
    ```

3.  **Launch with Docker Compose:**
    ```sh
    docker compose up --build
    ```
    Note: The first build may take 5-10 minutes to compile dlib.

4.  **Initialize the Database (First Run Only):** Open a new terminal tab and run:
    ```sh
    # Apply migrations
    docker compose exec web python manage.py migrate
    
    # Load initial student data
    docker compose exec web python manage.py loaddata datadump.json
    
    # Create an admin user
    docker compose exec web python manage.py createsuperuser
    ```

5.  **Access the App:** Go to http://localhost:8000


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