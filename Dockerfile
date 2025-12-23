# Use python 3.9 slim
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# ADDED: 'curl' is required for the healthcheck to work!
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY . .

# Expose Port 80
EXPOSE 80

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:80/_stcore/health || exit 1

# Run Streamlit on Port 80
CMD ["streamlit", "run", "dashboard.py", \
    "--server.port=80", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--server.enableCORS=false", \
    "--server.enableXsrfProtection=false", \
    "--server.fileWatcherType=none"]