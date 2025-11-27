# Use the geospatial base image
FROM ghcr.io/osgeo/gdal:ubuntu-small-latest

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1. Install compilers and system dependencies
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
# FIX: Added '--ignore-installed'.
# This forces pip to overwrite system packages (like numpy) instead of failing to uninstall them.
RUN pip3 install --break-system-packages --no-cache-dir --ignore-installed -r requirements.txt

# Copy the workflow steps
COPY steps/ /app/steps/
