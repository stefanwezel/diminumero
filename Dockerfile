# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml ./

# Install runtime dependencies using uv (system install)
RUN uv pip install --system -r pyproject.toml

# Copy the rest of the application code
COPY . .

# Set environment variable for Flask
ENV FLASK_APP=app.py

# Expose port 5005
EXPOSE 5005

# Production-only: apply DB migrations, then run gunicorn on 5005.
# `flask db upgrade` is idempotent — re-running on each start is safe and
# ensures a fresh container against a fresh DB has the latest schema before
# serving traffic. JSON-array form so SIGTERM is forwarded directly to
# gunicorn (PID 1), enabling graceful shutdown on `docker compose down`.
CMD ["sh", "-c", "flask db upgrade && exec gunicorn --bind 0.0.0.0:5005 --workers 2 app:app"]
