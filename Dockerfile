# KarmaForge Cloud Worker Dockerfile
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install curl and certificates for Reddit curl-backed engine
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy codebase
COPY . .

# Expose Hugging Face default health port
EXPOSE 7860

# Run the autonomous engine
CMD ["python", "main.py", "--run"]
