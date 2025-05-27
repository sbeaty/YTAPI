# Use Python 3.11 slim base image for query endpoint only
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Expose port 8000
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the YouTube Search & Analysis API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]