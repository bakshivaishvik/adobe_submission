# Stage 1: Build stage
FROM python:3.9-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.9-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application files
COPY src/finale_final.py .

# Create output directory
RUN mkdir -p /app/output

# Ensure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

ENTRYPOINT ["python", "finale_final.py"]