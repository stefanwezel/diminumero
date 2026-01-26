# Docker Setup

This project includes Docker containerization with separate configurations for development and production environments.

## Prerequisites

- Docker
- Docker Compose

## Quick Start

### Development Mode

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Build and run the development container:
   ```bash
   docker-compose -f docker-compose.dev.yml up --build
   ```

3. Access the application at: http://localhost:5001

**Development features:**
- Hot reloading (code changes reflect immediately)
- Debug mode enabled
- Volume mounting for live code updates
- Runs on port 5001

### Production Mode

1. Set your production secret key in `.env`:
   ```bash
   # Generate a secure secret key
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   
   Then update `.env`:
   ```
   FLASK_SECRET_KEY=your-generated-secret-key-here
   ```

2. Build and run the production container:
   ```bash
   docker-compose -f docker-compose.prod.yml up --build -d
   ```

3. Access the application at: http://localhost:5000

**Production features:**
- Gunicorn WSGI server (4 workers)
- Debug mode disabled
- No volume mounting (immutable container)
- Runs on port 5000
- Auto-restart enabled

## Docker Commands

### Development

```bash
# Start development server
docker-compose -f docker-compose.dev.yml up

# Rebuild and start
docker-compose -f docker-compose.dev.yml up --build

# Stop containers
docker-compose -f docker-compose.dev.yml down

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

### Production

```bash
# Start production server (detached)
docker-compose -f docker-compose.prod.yml up -d

# Rebuild and start
docker-compose -f docker-compose.prod.yml up --build -d

# Stop containers
docker-compose -f docker-compose.prod.yml down

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart container
docker-compose -f docker-compose.prod.yml restart
```

## Environment Variables

The application uses a `.env` file for configuration:

- `FLASK_SECRET_KEY`: Secret key for Flask sessions (required for production)

**Important:** Never commit `.env` to version control. Use `.env.example` as a template.

## Technology Stack

- **Base Image:** python:3.12-slim
- **Package Manager:** uv (fast Python package installer)
- **Development Server:** Flask development server
- **Production Server:** Gunicorn (4 workers)
- **Orchestration:** Docker Compose v3.8
