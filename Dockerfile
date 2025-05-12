# Use Python 3.11 slim for better performance and security
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install FFmpeg dependencies and create a non-root user
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-extra \
    wget \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -r -s /bin/bash appuser

# Create necessary directories
WORKDIR /app
RUN mkdir -p /app/temp_uploads /app/temp_converted /app/static /app/templates \
    && chown -R appuser:appuser /app \
    && chmod 777 /app/temp_uploads /app/temp_converted

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY --chown=appuser:appuser . .

# Make sure static and templates folders have the right permissions too
RUN chown -R appuser:appuser /app/static /app/templates \
    && chmod -R 755 /app/static /app/templates \
    # Create tasks file with appropriate permissions
    && touch /app/conversion_tasks.json \
    && chmod 666 /app/conversion_tasks.json \
    && chown appuser:appuser /app/conversion_tasks.json

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Use Gunicorn for production with only 1 worker to avoid task management issues
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]