# Use the geospatial base image
FROM ghcr.io/osgeo/gdal:ubuntu-small-latest

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1. Install system dependencies AND Build Tools
# 'build-essential' and 'python3-dev' are required to compile libraries like rasterio/shapely
RUN apt-get update && apt-get install -y \
    python3-pip \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# 2. Install Python libraries
# We upgrade pip, setuptools, and wheel first to avoid build errors
RUN pip3 install --break-system-packages --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --break-system-packages --no-cache-dir -r requirements.txt
