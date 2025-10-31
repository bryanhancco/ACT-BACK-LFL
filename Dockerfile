FROM python:3.11-slim

# Prevent python from writing pyc files to disc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required to build some Python packages.
# Keep the image small and clean up apt cache afterwards.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       gcc \
       libpq-dev \
       curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cache pip layer if requirements.txt doesn't change)
COPY requirements.txt /app/
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn uvicorn

# Copy project files
COPY . /app

# Create a non-root user for safer container runtime and give ownership of the app dir
RUN groupadd -r app && useradd -r -g app app || true \
    && chown -R app:app /app

USER app

EXPOSE 8000

# Use the same command style as the Procfile but ensure worker-tmp-dir flag is correct
CMD ["gunicorn", "--worker-tmp-dir", "/dev/shm", "--config", "gunicorn.config.py", "main:app"]
