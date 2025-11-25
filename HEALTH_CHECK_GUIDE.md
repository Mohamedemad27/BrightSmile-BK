# Health Check Endpoint Guide

## Quick Access

**Endpoint**: `GET /api/health/`
**Authentication**: Not required (Public endpoint)
**Documentation**: http://localhost:8000/swagger/ (Health Check section)

## Testing the Endpoint

### Using cURL

```bash
# Simple request
curl http://localhost:8000/api/health/

# Pretty formatted
curl http://localhost:8000/api/health/ | jq

# Check only status code
curl -o /dev/null -s -w "%{http_code}\n" http://localhost:8000/api/health/
```

### Using HTTPie

```bash
# Install httpie: pip install httpie
http GET http://localhost:8000/api/health/
```

### Using Python

```python
import requests

response = requests.get('http://localhost:8000/api/health/')
data = response.json()

print(f"Status: {data['status']}")
print(f"Environment: {data['environment']}")
print(f"Version: {data['version']}")

for service in data['services']:
    print(f"\n{service['service'].upper()}:")
    print(f"  Status: {service['status']}")
    print(f"  Response Time: {service['response_time']}ms")
    print(f"  Details: {service['details']}")
```

### Using Swagger UI

1. Start the server: `docker-compose up -d` or `python manage.py runserver`
2. Visit: http://localhost:8000/swagger/
3. Find "Health Check" section
4. Click "GET /api/health/"
5. Click "Try it out"
6. Click "Execute"

## Response Examples

### Healthy System

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "environment": "dev",
  "services": [
    {
      "service": "database",
      "status": "healthy",
      "response_time": 12.5,
      "details": "PostgreSQL with PostGIS 3.5.0"
    },
    {
      "service": "redis",
      "status": "healthy",
      "response_time": 3.2,
      "details": "Redis 7.2.4"
    },
    {
      "service": "application",
      "status": "healthy",
      "response_time": 0.5,
      "details": "Django 5.2.8"
    }
  ]
}
```

### Degraded System (Redis Down)

```json
{
  "status": "degraded",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "environment": "dev",
  "services": [
    {
      "service": "database",
      "status": "healthy",
      "response_time": 11.3,
      "details": "PostgreSQL with PostGIS 3.5.0"
    },
    {
      "service": "redis",
      "status": "unhealthy",
      "response_time": null,
      "details": "Error: Connection refused"
    },
    {
      "service": "application",
      "status": "healthy",
      "response_time": 0.4,
      "details": "Django 5.2.8"
    }
  ]
}
```

### Unhealthy System (Database Down)

```json
{
  "status": "unhealthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "environment": "prod",
  "services": [
    {
      "service": "database",
      "status": "unhealthy",
      "response_time": null,
      "details": "Error: could not connect to server"
    },
    {
      "service": "redis",
      "status": "healthy",
      "response_time": 2.8,
      "details": "Redis 7.2.4"
    },
    {
      "service": "application",
      "status": "healthy",
      "response_time": 0.3,
      "details": "Django 5.2.8"
    }
  ]
}
```

## What Each Service Checks

### Database (PostgreSQL + PostGIS)
- ✓ Connection establishment
- ✓ Query execution (`SELECT 1`)
- ✓ PostGIS extension availability and version
- ✓ Response time measurement

**Critical**: System returns `unhealthy` if database is down

### Redis
- ✓ Connection establishment
- ✓ Write operation (`cache.set()`)
- ✓ Read operation (`cache.get()`)
- ✓ Version detection
- ✓ Response time measurement

**Non-Critical**: System returns `degraded` if Redis is down

### Application
- ✓ Django runtime status
- ✓ Django version information

**Always Healthy**: If you can reach the endpoint, the app is running

## Status Levels

| Status | HTTP Code | Meaning |
|--------|-----------|---------|
| `healthy` | 200 | All services operational |
| `degraded` | 200 | Non-critical services down (e.g., Redis) |
| `unhealthy` | 503 | Critical services down (e.g., Database) |

## Integration Examples

### Docker Compose Health Check

```yaml
services:
  web:
    build: .
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Kubernetes Liveness Probe

```yaml
livenessProbe:
  httpGet:
    path: /api/health/
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### Kubernetes Readiness Probe

```yaml
readinessProbe:
  httpGet:
    path: /api/health/
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  successThreshold: 1
  failureThreshold: 3
```

### Monitoring Script

```bash
#!/bin/bash
# monitor.sh - Simple health monitoring script

ENDPOINT="http://localhost:8000/api/health/"
ALERT_EMAIL="admin@brightsmile.com"

while true; do
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $ENDPOINT)

  if [ "$RESPONSE" != "200" ]; then
    echo "ALERT: Health check failed with status $RESPONSE"
    # Send alert (requires mail command)
    echo "Health check failed at $(date)" | mail -s "Health Check Alert" $ALERT_EMAIL
  else
    echo "$(date): System healthy"
  fi

  sleep 60  # Check every minute
done
```

### Python Monitoring

```python
import time
import requests
from datetime import datetime

def monitor_health():
    """Monitor health endpoint and alert on issues."""
    endpoint = "http://localhost:8000/api/health/"

    while True:
        try:
            response = requests.get(endpoint, timeout=5)
            data = response.json()

            status = data['status']
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if status == 'unhealthy':
                print(f"[{timestamp}] CRITICAL: System unhealthy!")
                # Send alert to your monitoring system
            elif status == 'degraded':
                print(f"[{timestamp}] WARNING: System degraded")
                # Send warning
            else:
                print(f"[{timestamp}] OK: System healthy")

            # Print service details
            for service in data['services']:
                if service['status'] != 'healthy':
                    print(f"  - {service['service']}: {service['details']}")

        except Exception as e:
            print(f"[{timestamp}] ERROR: Could not reach health endpoint: {e}")

        time.sleep(60)  # Check every minute

if __name__ == '__main__':
    monitor_health()
```

## Testing Health Checks

### Unit Tests

```bash
# Run health check tests
python manage.py test apps.core.tests.HealthCheckTestCase

# Verbose output
python manage.py test apps.core.tests.HealthCheckTestCase --verbosity=2
```

### Manual Testing Scenarios

#### Test 1: Everything Healthy
```bash
# Start all services
docker-compose up -d

# Check health
curl http://localhost:8000/api/health/ | jq

# Expected: status = "healthy", all services healthy
```

#### Test 2: Redis Down
```bash
# Stop Redis
docker-compose stop redis

# Check health
curl http://localhost:8000/api/health/ | jq

# Expected: status = "degraded", Redis unhealthy

# Restart Redis
docker-compose start redis
```

#### Test 3: Database Down
```bash
# Stop database
docker-compose stop db

# Check health (may take a moment to timeout)
curl http://localhost:8000/api/health/ | jq

# Expected: status = "unhealthy", HTTP 503, Database unhealthy

# Restart database
docker-compose start db
```

## Troubleshooting

### Health Check Returns 404

**Cause**: URLs not properly configured

**Solution**:
```bash
# Verify core app is in INSTALLED_APPS
python manage.py shell
>>> from django.conf import settings
>>> 'apps.core' in settings.INSTALLED_APPS

# Check URL configuration
python manage.py show_urls | grep health
```

### Database Check Always Fails

**Cause**: Database not running or wrong credentials

**Solution**:
```bash
# Check database connection
docker-compose exec db psql -U postgres -d bright_smile_db -c "SELECT 1"

# Check environment variables
cat .env | grep DB_

# Test connection manually
python manage.py dbshell
```

### Redis Check Always Fails

**Cause**: Redis not running or wrong URL

**Solution**:
```bash
# Check Redis connection
redis-cli -h localhost -p 6379 ping

# For Docker
docker-compose exec redis redis-cli ping

# Check cache configuration
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value')
>>> cache.get('test')
```

### Slow Response Times

**Cause**: Database or Redis responding slowly

**Investigation**:
```bash
# Check response times in health check
curl http://localhost:8000/api/health/ | jq '.services[] | {service, response_time}'

# Monitor database
docker-compose exec db pg_top

# Monitor Redis
docker-compose exec redis redis-cli --latency
```

## Best Practices

1. **Load Balancers**: Configure health check interval to 10-30 seconds
2. **Kubernetes**: Use separate liveness and readiness probes
3. **Monitoring**: Set up alerts for `degraded` and `unhealthy` states
4. **Timeouts**: Set appropriate timeouts (5-10 seconds recommended)
5. **Caching**: Don't cache health check responses
6. **Logging**: Monitor health check endpoint logs for patterns

## Next Steps

1. Integrate with your monitoring system
2. Set up alerts for unhealthy states
3. Configure load balancer health checks
4. Add custom service checks as needed
5. Monitor response times and set up alerts

For more details, see `apps/core/README.md`
