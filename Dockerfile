FROM python:3.11-slim

LABEL maintainer="JellyCache-R"
LABEL description="Jellyfin media caching automation for Unraid"

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py ./
COPY logging_config.py ./

# Create directories for config and logs
RUN mkdir -p /config /logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CONFIG_PATH=/config/jellycache_settings.json

# Default command - run once (for scheduled execution)
# Use --dry-run for testing
CMD ["python", "plexcache_app.py", "--config", "/config/jellycache_settings.json"]
