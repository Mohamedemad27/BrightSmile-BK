# Bright Smile Backend

Django REST API with PostGIS support for geographic data, Celery for background tasks, and Docker for easy deployment.

## Features

- Django 5.2.8 with Django REST Framework
- PostGIS for geographic/spatial data support
- Celery for asynchronous task processing
- Redis for caching and message broker
- Docker and Docker Compose for containerization
- Swagger/ReDoc API documentation
- Development tools (Django Debug Toolbar, Silk)

## Prerequisites

### Option 1: Using Docker (Recommended)
- Docker Desktop or Docker Engine
- Docker Compose

### Option 2: Local Development
- Python 3.12+
- PostgreSQL 14+ with PostGIS extension
- Redis
- GDAL library (for GeoDjango)

## Quick Start with Docker

### 1. Clone the repository
```bash
git clone <repository-url>
cd Bright-Smile-BE
```

### 2. Configure environment variables
Copy the template and update with your values:
```bash
cp .env.template .env
```

Edit `.env` file and update the credentials as needed. The default values work with Docker setup.

### 3. Build and start the containers
```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Create database and run migrations
```bash
# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

### 5. Access the application
- API: http://localhost:8000/
- Admin: http://localhost:8000/admin/
- Swagger UI: http://localhost:8000/swagger/
- ReDoc: http://localhost:8000/redoc/
- Health Check: http://localhost:8000/api/health/

## Docker Services

The docker-compose setup includes:

- **web**: Django application (port 8000)
- **db**: PostgreSQL 17 with PostGIS 3.5 (port 5432)
- **redis**: Redis 7 (port 6379)
- **celery_worker**: Celery worker for background tasks
- **celery_beat**: Celery beat for scheduled tasks

## Managing Docker Services

### Start services
```bash
docker-compose up -d
```

### Stop services
```bash
docker-compose stop
```

### Restart services
```bash
docker-compose restart
```

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f celery_worker
```

### Execute commands in containers
```bash
# Django management commands
docker-compose exec web python manage.py <command>

# Shell access
docker-compose exec web bash
docker-compose exec db psql -U postgres -d bright_smile_db
```

### Stop and remove containers
```bash
docker-compose down

# Remove volumes as well (WARNING: deletes database data)
docker-compose down -v
```

## Local Development Setup (Without Docker)

### 1. Install system dependencies

#### macOS
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install postgresql@17
brew install postgis
brew install gdal
brew install redis

# Start services
brew services start postgresql@17
brew services start redis
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    postgresql-17 \
    postgresql-17-postgis-3 \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    redis-server
```

### 2. Create virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Python dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Set up PostgreSQL database
```bash
# Create database and enable PostGIS
createdb bright_smile_db
psql bright_smile_db -c "CREATE EXTENSION postgis;"

# Or if using postgres user
sudo -u postgres createdb bright_smile_db
sudo -u postgres psql bright_smile_db -c "CREATE EXTENSION postgis;"
```

### 5. Configure environment
```bash
cp .env.template .env
# Edit .env and update DB_HOST=localhost
```

### 6. Run migrations
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 7. Run development server
```bash
python manage.py runserver
```

## Working with Celery (Background Tasks)

Celery is configured for handling asynchronous and scheduled tasks.

### Starting Celery (Docker)
Celery worker and beat are automatically started with docker-compose.

```bash
# View worker logs
docker-compose logs -f celery_worker

# View beat logs
docker-compose logs -f celery_beat

# Restart worker
docker-compose restart celery_worker
```

### Starting Celery (Local Development)

You need to run these in separate terminal windows:

#### Terminal 1: Celery Worker
```bash
celery -A project worker --loglevel=info
```

#### Terminal 2: Celery Beat (for scheduled tasks)
```bash
celery -A project beat --loglevel=info
```

#### Terminal 3: Django Development Server
```bash
python manage.py runserver
```

### Creating Background Tasks

Create a `tasks.py` file in your Django app:

```python
from celery import shared_task

@shared_task
def process_data(data_id):
    """Example background task"""
    # Your task logic here
    return f"Processed data {data_id}"
```

Call the task:
```python
from myapp.tasks import process_data

# Execute asynchronously
result = process_data.delay(123)

# Get result
print(result.get())
```

### Scheduled Tasks

Edit `project/celery.py` and add to `beat_schedule`:

```python
app.conf.beat_schedule = {
    'cleanup-old-data': {
        'task': 'apps.myapp.tasks.cleanup_old_data',
        'schedule': crontab(hour=2, minute=0),  # Run at 2:00 AM daily
    },
}
```

## Project Structure

```
Bright-Smile-BE/
├── project/
│   ├── settings/          # Settings configuration
│   │   ├── common.py      # Common settings
│   │   ├── dev.py         # Development settings
│   │   └── prod.py        # Production settings
│   ├── celery.py          # Celery configuration
│   └── urls.py            # URL routing
├── apps/                  # Django applications
│   └── core/              # Core app with health check
│       ├── views.py       # Health check endpoint
│       ├── serializers.py # API serializers
│       └── tests.py       # Tests
├── utils/                 # Utility functions and helpers
├── static/                # Static files
├── media/                 # User uploads
├── logs/                  # Application logs
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env                   # Environment variables (not in git)
├── .env.template          # Template for environment variables
├── README.md              # Full documentation
└── HEALTH_CHECK_GUIDE.md  # Health check documentation
```

## Common Commands

### Django
```bash
# Make migrations
python manage.py makemigrations

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Run tests
python manage.py test

# Django shell
python manage.py shell
```

### Docker
```bash
# Build without cache
docker-compose build --no-cache

# Remove unused images and volumes
docker system prune -a --volumes

# Scale celery workers
docker-compose up -d --scale celery_worker=3
```

## API Endpoints

### Health Check

Comprehensive health monitoring endpoint that checks all critical services.

**Endpoint**: `GET /api/health/`

**Example**:
```bash
curl http://localhost:8000/api/health/ | jq
```

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "environment": "dev",
  "services": [
    {"service": "database", "status": "healthy", "response_time": 12.5},
    {"service": "redis", "status": "healthy", "response_time": 3.2},
    {"service": "application", "status": "healthy", "response_time": 0.5}
  ]
}
```

**What it checks**:
- ✓ PostgreSQL database with PostGIS
- ✓ Redis (Celery broker)
- ✓ Application status

For detailed documentation, see [HEALTH_CHECK_GUIDE.md](HEALTH_CHECK_GUIDE.md)

## API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/
- **Health Check**: http://localhost:8000/api/health/

## Development Tools

When `DEBUG=True`, these tools are available:

- **Django Admin**: http://localhost:8000/admin/
- **Django Debug Toolbar**: http://localhost:8000/__debug__/
- **Silk Profiler**: http://localhost:8000/silk/

## Environment Variables

See `.env.template` for all available environment variables. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment mode (dev/prod) | `dev` |
| `SECRET_KEY` | Django secret key | Required |
| `DEBUG` | Debug mode | `True` |
| `DB_NAME` | Database name | `bright_smile_db` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | Required |
| `DB_HOST` | Database host | `localhost` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/0` |

## Production Deployment

For production:

1. Set `ENVIRONMENT=prod` in `.env`
2. Generate a secure `SECRET_KEY`
3. Set `DEBUG=False`
4. Configure `ALLOWED_HOSTS`
5. Set up proper database credentials
6. Configure email settings
7. Enable SSL/HTTPS
8. Use a production-grade web server (gunicorn is included)
9. Set up proper logging

## Troubleshooting

### GDAL/GEOS errors
If you get GDAL or GEOS library errors:
- macOS: `brew reinstall gdal`
- Ubuntu: `sudo apt-get install --reinstall gdal-bin libgdal-dev`
- Windows: Install OSGeo4W and set GDAL_LIBRARY_PATH in .env

### Database connection errors
- Ensure PostgreSQL is running
- Check DB credentials in .env
- Verify PostGIS extension: `psql bright_smile_db -c "SELECT PostGIS_version();"`

### Celery not processing tasks
- Check Redis is running: `redis-cli ping`
- Verify Celery worker is running
- Check broker URL in settings

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests
4. Submit a pull request

## License

[Your License Here]
