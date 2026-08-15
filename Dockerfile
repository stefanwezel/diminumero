# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# WeasyPrint (worksheet PDFs) needs Pango/HarfBuzz at runtime, and fonts —
# python:3.12-slim ships literally none, so without this block every PDF comes
# out as blank boxes while still looking fine in a local dev checkout. Each
# font package is here for a specific set of languages:
#   fonts-dejavu-core  Latin incl. Latin Extended-A — Welsh ŵŷ, Turkish ğşı,
#                      Nordic æøå, Irish/Spanish accents (~2 MB)
#   fonts-noto-cjk     Japanese, Korean, Chinese (~91 MB, the bulk of the image
#                      growth; there is no smaller Debian package covering all
#                      three)
#   fonts-lohit-deva   Devanagari for Nepali (~0.2 MB)
# fc-cache runs at build time so the first PDF request doesn't pay for it.
# tools/check_worksheet_fonts.py is the gate — run it against the BUILT image
# (`docker run --rm <image> python tools/check_worksheet_fonts.py`). Nothing in
# pytest covers this: CI has no CJK fonts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        fontconfig \
        fonts-dejavu-core \
        fonts-noto-cjk \
        fonts-lohit-deva \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

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
# Flags:
#   --access-logfile / --error-logfile -  send gunicorn logs to stdout/stderr
#     so `docker logs` (and Coolify) captures every request and crash.
#   --timeout 60                         tolerate slow Auth0 / DB calls
#                                        without killing the worker at 30s.
#   --graceful-timeout 30                give in-flight requests time to
#                                        finish on SIGTERM.
#   --max-requests / --max-requests-jitter  recycle each worker periodically
#                                        to bound any slow memory leak.
CMD ["sh", "-c", "flask db upgrade && exec gunicorn --bind 0.0.0.0:5005 --workers 3 --timeout 60 --graceful-timeout 30 --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile - app:app"]
