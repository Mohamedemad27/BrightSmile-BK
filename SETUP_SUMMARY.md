# Bright Smile Backend - Setup Summary

## What Was Configured

### 1. Django Settings with GIS Support
- **Location**: `project/settings/`
- **Files**: `common.py`, `dev.py`, `prod.py`, `__init__.py`
- **Features**:
  - PostgreSQL with PostGIS database backend
  - Django REST Framework
  - CORS configuration
  - Development tools (Debug Toolbar, Silk)
  - Environment-based settings (dev/prod)

### 2. Celery Configuration
- **Location**: `project/celery.py`, `project/__init__.py`
- **Features**:
  - Redis as broker and result backend
  - Automatic task discovery
  - Beat schedule for periodic tasks
  - Debug task included

### 3. Docker Setup
- **Files**: `Dockerfile`, `docker-compose.yml`
- **Services**:
  - **web**: Django app on port 8000
  - **db**: PostgreSQL 17 + PostGIS 3.5 on port 5432
  - **redis**: Redis 7 on port 6379
  - **celery_worker**: Background task worker
  - **celery_beat**: Scheduled task scheduler

### 4. Requirements (Latest Versions)
- Django 5.2.8
- djangorestframework 3.16.1
- psycopg2-binary 2.9.10
- GDAL 3.10.0
- celery 5.4.0
- redis 5.2.1
- And more...

### 5. Environment Configuration
- `.env` - Local development with actual credentials
- `.env.template` - Template for sharing
- `.env.docker` - Docker-specific configuration
- All sensitive data in .gitignore

## Quick Start

### Option 1: Using Docker (Recommended)

1. **Start all services**:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

2. **Run migrations**:
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   ```

3. **Access**:
   - API: http://localhost:8000
   - Admin: http://localhost:8000/admin
   - Swagger: http://localhost:8000/swagger

### Option 2: Local Development

1. **Setup environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Start services** (3 separate terminals):
   ```bash
   # Terminal 1: Celery Worker
   celery -A project worker --loglevel=info

   # Terminal 2: Celery Beat
   celery -A project beat --loglevel=info

   # Terminal 3: Django
   python manage.py runserver
   ```

   Or use the helper script:
   ```bash
   ./start-local.sh
   ```

## Working with Celery

### View Celery Logs (Docker)
```bash
docker-compose logs -f celery_worker
docker-compose logs -f celery_beat
```

### Creating Tasks

1. Create `tasks.py` in your Django app:
   ```python
   from celery import shared_task

   @shared_task
   def send_email_notification(user_id):
       # Your task logic
       return f"Email sent to user {user_id}"
   ```

2. Call the task:
   ```python
   from myapp.tasks import send_email_notification

   # Execute asynchronously
   send_email_notification.delay(123)
   ```

### Scheduled Tasks

Edit `project/celery.py`:
```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'daily-cleanup': {
        'task': 'apps.myapp.tasks.cleanup',
        'schedule': crontab(hour=2, minute=0),  # 2:00 AM daily
    },
}
```

## Database Setup

### Using Docker
The database is automatically created with PostGIS extension.

### Local Setup
```bash
# Create database
createdb bright_smile_db

# Enable PostGIS
psql bright_smile_db -c "CREATE EXTENSION postgis;"

# Verify
psql bright_smile_db -c "SELECT PostGIS_version();"
```

## Common Commands

### Docker
```bash
# View all logs
docker-compose logs -f

# Restart a service
docker-compose restart web

# Run Django commands
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser

# Access database
docker-compose exec db psql -U postgres -d bright_smile_db

# Stop everything
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Local Development
```bash
# Migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver

# Django shell
python manage.py shell

# Collect static files
python manage.py collectstatic
```

## Project Structure

```
Bright-Smile-BE/
├── project/                    # Django project
│   ├── settings/              # Split settings
│   │   ├── common.py          # Common settings
│   │   ├── dev.py             # Development
│   │   └── prod.py            # Production
│   ├── __init__.py            # Celery import
│   ├── celery.py              # Celery config
│   ├── urls.py                # URL routing
│   ├── wsgi.py                # WSGI config
│   └── asgi.py                # ASGI config
├── static/                    # Static files
├── media/                     # User uploads
├── logs/                      # Application logs
├── manage.py                  # Django management
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker image
├── docker-compose.yml         # Docker services
├── .env                       # Environment variables (local)
├── .env.template              # Template
├── .env.docker                # Docker environment
├── start-local.sh             # Local start script
└── README.md                  # Full documentation
```

## API Documentation

When running, visit:
- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/

## Development Tools

With `DEBUG=True`:
- **Admin Panel**: http://localhost:8000/admin/
- **Debug Toolbar**: http://localhost:8000/__debug__/
- **Silk Profiler**: http://localhost:8000/silk/

## Environment Variables

Key variables (see `.env.template` for all):

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | dev or prod | `dev` |
| `SECRET_KEY` | Django secret | Required |
| `DB_NAME` | Database name | `bright_smile_db` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | Required |
| `DB_HOST` | Database host | `localhost` (or `db` in Docker) |
| `CELERY_BROKER_URL` | Redis URL | `redis://localhost:6379/0` |

## Next Steps

1. **Create your first Django app**:
   ```bash
   python manage.py startapp myapp
   # Add 'myapp' to INSTALLED_APPS in settings/common.py
   ```

2. **Create models with GIS fields**:
   ```python
   from django.contrib.gis.db import models

   class Location(models.Model):
       name = models.CharField(max_length=100)
       point = models.PointField()

       def __str__(self):
           return self.name
   ```

3. **Create API endpoints**:
   ```python
   from rest_framework import viewsets
   from .models import Location
   from .serializers import LocationSerializer

   class LocationViewSet(viewsets.ModelViewSet):
       queryset = Location.objects.all()
       serializer_class = LocationSerializer
   ```

4. **Add background tasks** in `myapp/tasks.py`

5. **Test everything works**:
   ```bash
   docker-compose up -d
   docker-compose exec web python manage.py migrate
   ```

## Troubleshooting

### GDAL Errors
- macOS: `brew reinstall gdal`
- Ubuntu: `sudo apt-get install --reinstall gdal-bin libgdal-dev`

### Database Connection
- Check PostgreSQL is running
- Verify credentials in `.env`
- Check PostGIS: `psql bright_smile_db -c "SELECT PostGIS_version();"`

### Celery Issues
- Check Redis: `redis-cli ping`
- View worker logs: `docker-compose logs -f celery_worker`
- Verify broker URL in settings

### Docker Issues
- Rebuild: `docker-compose build --no-cache`
- Clean up: `docker system prune -a`
- Check logs: `docker-compose logs -f`

## Additional Resources

- Full README: See `README.md`
- Django Docs: https://docs.djangoproject.com/
- GeoDjango: https://docs.djangoproject.com/en/stable/ref/contrib/gis/
- Celery Docs: https://docs.celeryq.dev/
- DRF Docs: https://www.django-rest-framework.org/

## Support

For issues or questions, refer to:
1. `README.md` for detailed documentation
2. Docker logs: `docker-compose logs -f`
3. Django logs in `logs/` directory
