# Use the geospatial base image (includes Python + GDAL)
FROM ghcr.io/osgeo/gdal:ubuntu-small-latest

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install pip
RUN apt-get update && apt-get install -y python3-pip && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# (Optional) We don't copy the scripts here because CWL injects them.
# This image serves as the "Runtime Environment".