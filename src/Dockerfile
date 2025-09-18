# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=tradevision.settings

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
        curl \
        netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user first
RUN adduser --disabled-password --gecos '' --uid 1000 appuser

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Make scripts executable
RUN chmod +x /app/scripts/wait-for-it.sh \
    && chmod +x /app/scripts/entrypoint.sh \
    && chmod +x /app/scripts/healthcheck.sh

# Change ownership to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port 8000
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /app/scripts/healthcheck.sh

# Default command
CMD ["/app/scripts/entrypoint.sh"]