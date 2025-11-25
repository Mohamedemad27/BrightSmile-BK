# Core App

The Core app provides essential utility endpoints and functionality for the Bright Smile Backend.

## Features

### Health Check Endpoint

Comprehensive health monitoring endpoint that checks the status of all critical services.

**Endpoint**: `GET /api/health/`

**Authentication**: None (Public endpoint)

**Response Codes**:
- `200 OK`: All services are healthy or degraded
- `503 Service Unavailable`: Critical services are down

**What It Checks**:
1. **Database (PostgreSQL with PostGIS)**
   - Connection test
   - Query execution
   - PostGIS version detection

2. **Redis**
   - Connection test
   - Cache read/write operations
   - Version detection

3. **Application**
   - Django version
   - General application status

**Response Format**:
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
      "details": "PostgreSQL 17 with PostGIS 3.5"
    },
    {
      "service": "redis",
      "status": "healthy",
      "response_time": 3.2,
      "details": "Redis 7.0"
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

**Status Values**:
- `healthy`: All services operational
- `degraded`: Some non-critical services down (e.g., Redis down but database up)
- `unhealthy`: Critical services down (e.g., database down)

## Use Cases

### 1. Kubernetes/Docker Health Probes

```yaml
livenessProbe:
  httpGet:
    path: /api/health/
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /api/health/
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### 2. Load Balancer Health Checks

Configure your load balancer to poll `/api/health/` and remove unhealthy instances.

### 3. Monitoring & Alerting

Use the endpoint with monitoring tools like:
- Prometheus
- Datadog
- New Relic
- Custom monitoring scripts

Example curl:
```bash
curl http://localhost:8000/api/health/
```

### 4. CI/CD Pipeline Validation

```bash
# Wait for service to be healthy
while true; do
  STATUS=$(curl -s http://localhost:8000/api/health/ | jq -r '.status')
  if [ "$STATUS" = "healthy" ]; then
    echo "Service is healthy!"
    break
  fi
  echo "Waiting for service... (status: $STATUS)"
  sleep 5
done
```

## Testing

Run tests for the health check endpoint:

```bash
# Run all core app tests
python manage.py test apps.core

# Run specific test
python manage.py test apps.core.tests.HealthCheckTestCase

# Run with coverage
coverage run --source='apps.core' manage.py test apps.core
coverage report
```

## API Documentation

The health check endpoint is fully documented in Swagger UI:
- Visit: http://localhost:8000/swagger/
- Navigate to "Health Check" section
- Try it out directly from the UI

## Future Enhancements

Potential additions to the health check:
- [ ] Celery worker status check
- [ ] External API dependency checks
- [ ] Disk space monitoring
- [ ] Memory usage monitoring
- [ ] Custom service checks
