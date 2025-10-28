FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY Pipfile Pipfile.lock ./
RUN pip install pipenv && \
    pipenv install --system --deploy

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Use gunicorn to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "wsgi:app"]

