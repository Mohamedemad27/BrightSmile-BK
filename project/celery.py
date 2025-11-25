"""
Celery configuration for Bright Smile project.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

app = Celery('project')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Example: Run every 30 minutes
    # 'sample-task': {
    #     'task': 'apps.yourapp.tasks.sample_task',
    #     'schedule': crontab(minute='*/30'),
    # },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """
    Debug task for testing Celery configuration.
    """
    print(f'Request: {self.request!r}')
