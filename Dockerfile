# Use a specific, stable Debian version (Bookworm) so it doesn't break randomly
FROM python:3.10-slim-bookworm

# Set environment variables to prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies
# CHANGED: Added 'git' to the list below
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    libx11-dev \
    libopenblas-dev \
    liblapack-dev \
    libgtk-3-dev \
    libboost-python-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Default command to run the web server
CMD ["gunicorn", "smart_roll.wsgi:application", "--bind", "0.0.0.0:8000"]