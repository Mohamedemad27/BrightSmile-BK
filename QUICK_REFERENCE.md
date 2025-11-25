# Quick Reference Card

## Health Check Endpoint

### Endpoint
```
GET /api/health/
```

### Quick Test
```bash
# Simple test
curl http://localhost:8000/api/health/

# Pretty JSON
curl http://localhost:8000/api/health/ | jq

# Just status
curl -s http://localhost:8000/api/health/ | jq -r '.status'
```

### Expected Response (Healthy)
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

## Status Codes

| Status | HTTP | Meaning |
|--------|------|---------|
| `healthy` | 200 | ✅ All services up |
| `degraded` | 200 | ⚠️ Redis down |
| `unhealthy` | 503 | ❌ Database down |

## What's Checked

- ✅ **Database**: PostgreSQL + PostGIS connection and queries
- ✅ **Redis**: Cache read/write operations
- ✅ **Application**: Django runtime status

## Access Points

| Service | URL |
|---------|-----|
| Health Check | http://localhost:8000/api/health/ |
| Swagger UI | http://localhost:8000/swagger/ |
| ReDoc | http://localhost:8000/redoc/ |
| Admin | http://localhost:8000/admin/ |

## Docker Commands

```bash
# Start all services
docker-compose up -d

# Check health
curl http://localhost:8000/api/health/ | jq

# View logs
docker-compose logs -f web

# Run migrations
docker-compose exec web python manage.py migrate

# Run tests
docker-compose exec web python manage.py test apps.core
```

## Files to Check

| File | Description |
|------|-------------|
| `GITHUB_PROJECTS_GUIDE.md` | Team task tracking and workflow guide |
| `CORE_APP_SUMMARY.md` | Complete core app overview |
| `HEALTH_CHECK_GUIDE.md` | Detailed health check guide |
| `SETUP_SUMMARY.md` | Initial project setup guide |
| `README.md` | Full project documentation |
| `apps/core/README.md` | Core app documentation |

## Testing Scenarios

### Test 1: All Healthy
```bash
docker-compose up -d
curl http://localhost:8000/api/health/ | jq -r '.status'
# Expected: healthy
```

### Test 2: Redis Down
```bash
docker-compose stop redis
curl http://localhost:8000/api/health/ | jq -r '.status'
# Expected: degraded
docker-compose start redis
```

### Test 3: Database Down
```bash
docker-compose stop db
curl http://localhost:8000/api/health/ | jq -r '.status'
# Expected: unhealthy (HTTP 503)
docker-compose start db
```

## Common Issues

### 404 Error
```bash
# Check if core app is registered
docker-compose exec web python manage.py shell -c "from django.conf import settings; print('apps.core' in settings.INSTALLED_APPS)"
```

### Database Connection Failed
```bash
# Check database is running
docker-compose ps db

# Test connection
docker-compose exec db psql -U postgres -d bright_smile_db -c "SELECT 1"
```

### Redis Connection Failed
```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
```

## Integration Examples

### Kubernetes Liveness Probe
```yaml
livenessProbe:
  httpGet:
    path: /api/health/
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

### Monitoring Script
```bash
#!/bin/bash
while true; do
  STATUS=$(curl -s http://localhost:8000/api/health/ | jq -r '.status')
  echo "$(date): $STATUS"
  [ "$STATUS" != "healthy" ] && echo "ALERT: System $STATUS!"
  sleep 60
done
```

## Quick Wins

1. ✅ Health check is **public** - no auth needed
2. ✅ Returns proper **HTTP status codes**
3. ✅ **Response times** for each service
4. ✅ Detailed **error messages**
5. ✅ Full **Swagger documentation**
6. ✅ Complete **test coverage**

## Need Help?

- 📖 Full Guide: `HEALTH_CHECK_GUIDE.md`
- 📋 Core App: `CORE_APP_SUMMARY.md`
- 🚀 Setup: `SETUP_SUMMARY.md`
- 📚 Docs: `README.md`
- 🌐 Swagger: http://localhost:8000/swagger/
