# Dockerfile for Railway Deployment
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn

# Copy application code
COPY sim/ ./sim/
COPY api/ ./api/
COPY static/ ./static/

# Set Python path
ENV PYTHONPATH=/app
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the API server
CMD ["python", "-m", "api.main"]
