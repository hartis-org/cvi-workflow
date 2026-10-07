# Use the geospatial base image
FROM ghcr.io/osgeo/gdal:ubuntu-small-latest

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install compilers and system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python libraries.
COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir --ignore-installed -r requirements.txt

# Keep the workflow implementation available in the runtime image.
COPY steps/ /app/steps/
