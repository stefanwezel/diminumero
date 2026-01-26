# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml ./

# Sync dependencies using uv
RUN uv pip install --system -r pyproject.toml

# Copy the rest of the application code
COPY . .

# Set environment variable for Flask
ENV FLASK_APP=app.py

# Expose the port the app runs on
EXPOSE 5000

# Set an environment variable based on the MODE argument
ARG MODE
ENV MODE=${MODE}

# Print the MODE value to verify it's set correctly
RUN echo "MODE is set to ${MODE}"

# Default command depending on MODE
CMD if [ "$MODE" = "development" ]; then \
        export FLASK_ENV=development && export FLASK_DEBUG=1 && flask run --host=0.0.0.0; \
    else \
        gunicorn --bind 0.0.0.0:5000 --workers 4 app:app; \
    fi
