# Dockerfile

# 1. Base Image: Use a specific Python version (adjust if needed)
FROM python:3.12-slim

# 2. Set Environment Variables (Optional but good practice)
ENV PYTHONDONTWRITEBYTECODE 1  # Prevents python from writing .pyc files
ENV PYTHONUNBUFFERED 1      # Force stdin, stdout, stderr to be totally unbuffered

# 3. Set Working Directory
WORKDIR /app

# 4. Install System Dependencies (if any needed by your libraries)
# matplotlib might need some fonts or build tools on minimal images,
# but often works fine on -slim with the 'Agg' backend. Add if needed:
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libcairo2-dev \
        pkg-config \
        # ---> ADD THESE LINES <---
        libgirepository1.0-dev \
        gobject-introspection \
        # ---> END ADDED LINES <---
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# 5. Install Python Dependencies
# Copy only requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy Application Code
# Copy everything from the current directory (.) into the container's WORKDIR (/app)
COPY . .

# 7. Create a non-root user and switch to it
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# 8. Command to Run the Application
# This will execute `python main.py` when the container starts
CMD ["python", "main.py"]