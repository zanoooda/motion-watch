FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV with V4L2 support
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    v4l-utils \
    libv4l-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user and add to video group
RUN useradd -m -u 1000 appuser && \
    groupadd -g 44 video || true && \
    usermod -a -G video appuser && \
    chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "detector.main"]
