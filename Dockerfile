# Use python 3.9 slim for a small footprint
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies (GCC is needed for WordCloud)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual app code
COPY . .

# Expose Port 80 (Standard HTTP)
EXPOSE 80

# Healthcheck to allow Docker to know if the app is alive
HEALTHCHECK CMD curl --fail http://localhost:80/_stcore/health || exit 1

# Run Streamlit on Port 80, accessible externally (0.0.0.0)
CMD ["streamlit", "run", "dashboard.py", \
    "--server.port=80", \
    "--server.address=0.0.0.0", \
    "--server.headless=true"]