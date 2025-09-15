# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        gcc \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install psycopg2 explicitly (in case it's missing from requirements.txt)
RUN pip install --no-cache-dir psycopg2-binary

# Copy project files
COPY . /app/

# Make wait script executable
RUN chmod +x /app/wait-for-it.py

# Create static and media directories
RUN mkdir -p /app/static /app/media

# Create directories for static and media files
RUN mkdir -p /app/staticfiles /app/media

# Note: We'll run collectstatic after migrations in docker-compose

# Create directories for static and media files
RUN mkdir -p /app/staticfiles /app/media

# Expose port 7373
EXPOSE 7373

# Default command (will be overridden by docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:7373"]