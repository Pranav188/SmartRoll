University Project Title: Facial-Attendance-&-CheckIn-Engine

# SmartRoll: AI-Powered Facial Recognition Attendance System

SmartRoll is an AI-powered tool that automates classroom attendance using Python, OpenCV, and facial recognition. Simply upload a classroom photo to instantly receive a comprehensive attendance report, eliminating manual roll-call with fast and accurate computer vision.

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [License](#license)

---

## Features

- Automated attendance for an entire classroom in seconds from a single image.
- AI-powered recognition using a pre-trained deep learning model with the **face_recognition** library for robust identification.
- Detailed, timestamped CSV report listing each student as "Present" or "Absent".
- Simple enrollment: add new students by creating folders in `/dataset` and dropping in their photos—no database configuration needed.
- Adjustable recognition tolerance to control false positives for different environments.

---

## How It Works?

### Enrollment (One-Time Setup)
- Run `encode_faces.py` to scan the `/dataset` directory.
- For each student's image, a unique 128-point facial encoding is generated.
- All encodings are saved in `encodings.pickle` (the face database).

### Recognition (Daily Use)
- Instructors submit a classroom photo to `mark_attendance.py`.
- The script detects all faces, computes new encodings, and compares them with the database.
- Matched students are marked as present; unmatched are marked absent.
- The final report is printed to the terminal and saved as a CSV file.

---

## Technology Stack

- Python (backend)
- OpenCV (computer vision)
- face_recognition (powered by dlib)
- Pickle (data serialization)

---

## Getting Started

### Prerequisites

- Python 3.8+
- pip and venv (virtual environment)

### Installation

1. Clone the repository
   
   `git clone https://github.com/Pranav188/SmartRoll.git`
   
   `cd SmartRoll`

2. Create a virtual enviroment
   
   `python3 -m venv .venv`
   
   `source .venv/bin/activate`


4. Install necesary libraries
   
   `pip install opencv-python numpy face_recognition`

Note: If on macOS and face_recognition (dlib) install fails, install cmake first

`brew install cmake`


### Enrollment

1. Create a unique folder inside `dataset/` for each student, and add 2–3 clear, well-lit photos.
2. Run:
    ```
    python encode_faces.py
    ```

### Mark Attendance

1. Add your classroom photo (e.g., `classroom.jpg`) to the main project folder.
2. Update the `ALL_STUDENTS` list in `mark_attendance.py` to match the folder names.
3. Run:
    ```
    python mark_attendance.py
    ```

---

## License

MIT

