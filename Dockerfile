FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash wms
RUN chown -R wms:wms /app
USER wms

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "wms_app.main:app", "--host", "0.0.0.0", "--port", "8000"]