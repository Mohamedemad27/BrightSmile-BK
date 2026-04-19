# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Ensure Playwright downloads browsers into a shared path that is accessible
# to the non-root runtime user.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install system dependencies required for GeoDjango
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    pkg-config \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libcairo2-dev \
    postgresql-client \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# Set GDAL environment variables
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install runtime dependencies for Playwright/Chromium on Debian.
# We intentionally avoid `playwright install --with-deps` because it tries to
# install some Ubuntu-only font packages (e.g. ttf-unifont, ttf-ubuntu-font-family)
# which are not available on Debian (causes image build to fail).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libfontconfig1 \
    libfreetype6 \
    fonts-liberation \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-noto \
    fonts-noto-color-emoji \
    fonts-unifont \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Chromium for Playwright PDF rendering into the shared browsers path.
RUN mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} && \
    python -m playwright install chromium

# Copy project files
COPY . /app/

# Create necessary directories
RUN addgroup --system app && useradd --system --gid app --create-home --home-dir /home/app app && \
    mkdir -p /app/staticfiles /app/media /app/logs /home/app/.config/matplotlib ${PLAYWRIGHT_BROWSERS_PATH} && \
    chown -R app:app /app /home/app ${PLAYWRIGHT_BROWSERS_PATH}

ENV HOME=/home/app
ENV MPLCONFIGDIR=/home/app/.config/matplotlib

# Run as non-root
USER app

# Collect static files (optional - can be done during deployment)
# RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "project.wsgi:application"]
