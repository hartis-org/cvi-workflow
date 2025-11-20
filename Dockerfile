# Use the geospatial base image
FROM ghcr.io/osgeo/gdal:ubuntu-small-latest

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1. Install compilers and system dependencies
# We need python3-pip and build tools
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
# FIX: We removed the '--upgrade pip setuptools wheel' command.
# The system versions are recent enough, and upgrading them causes conflicts.
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt
