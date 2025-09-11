University Project Title: Facial-Attendance-&-CheckIn-Engine

 # *****SmartRoll: AI-Powered Facial Recognition Attendance System*****


This project automates classroom attendance using Python, OpenCV, and facial recognition. It analyzes a single photograph to identify students by comparing faces against an enrolled dataset in a supervised learning model. The engine then generates a complete report, marking all students as present or absent, streamlining administrative tasks with computer vision.

**Key Features**

Automated Attendance: Mark attendance for an entire classroom in seconds from a single image.

AI-Powered Recognition: Utilizes a powerful, pre-trained deep learning model via the **face_recognition** library for highly accurate identification.

Detailed Report Generation: Automatically creates a timestamped CSV file listing all students as either "Present" or "Absent".

Simple Enrollment Process: To enroll a new student, simply create a folder with their name and add their photos in the /dataset folder (in main folder). No complex database entries are needed.

Configurable Accuracy: The recognition tolerance can be easily adjusted to prevent false positives and tune the system for different environments.

**How It Works:**

The system operates in two main phases:

**1.Enrollment** (One-Time Setup):

The encode_faces.py script scans the /dataset folder.

For each student's image, it detects the face and computes a unique 128-point facial encoding.

All known encodings are saved into a single encodings.pickle file, which acts as our "face database."

**2.Recognition** (Daily Use):

An instructor provides a classroom photo to the mark_attendance_from_photo.py script.

The script detects every face in the image and computes their encodings on the fly.

Each of these new encodings is compared against the known encodings in the database to find matches.

The list of matched (present) students is compared against the master class roster to determine who is absent.

The final report is displayed in the terminal and saved to a CSV file.

**Technology Stack**

Backend: Python

Computer Vision: OpenCV

Facial Recognition: face_recognition (built on dlib's state-of-the-art face recognition model)

Data Serialization: Pickle

**Getting Started:**

Follow these steps to get the project running on your local machine.

Prerequisites

Python 3.8+

pip and venv

Installation & Usage

Clone the repository:

git clone [https://github.com/Pranav188/SmartRoll.git](https://github.com/Pranav188/SmartRoll.git)
cd SmartRoll

Create and activate a virtual environment:

# For macOS/Linux
`python3 -m venv .venv`
`source .venv/bin/activate`

# For Windows
`python -m venv .venv`
`.\.venv\Scripts\activate`
#

Install the required libraries:

`pip install opencv-python numpy face_recognition`

**Note for macOS users: If the installation fails while building dlib, you need to install cmake first.
for that.**

`brew install cmake `

Enroll Students:

Create a sub-folder inside the dataset/ directory for each student (e.g., dataset/pranav/).

Place 2-3 clear, well-lit photos of the student inside their respective folder.

Run the Enrollment Script:

This will create the encodings.pickle file. You only need to run this when you add new students or photos.

`python encode_faces.py`

Mark Attendance:

Place your classroom photo (e.g., classroom.jpg) in the main project folder.

Crucially, open mark_attendance_from_photo.py and update the ALL_STUDENTS list to match your dataset folder names exactly.

Run the main script:

`python mark_attendance_from_photo.py`

The results will be printed in your terminal, and a CSV report will be saved.

