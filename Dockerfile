FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for heavy packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend
COPY backend/ .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV COLLECT_FRESH_DATA=false
ENV USE_SAMPLE_FALLBACK=true

# Expose port
EXPOSE 8000

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
