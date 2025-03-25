from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('geosdata')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Configure Celery Beat schedule
app.conf.beat_schedule = {
    'sync-satellite-daily': {
        'task': 'data_pipeline.tasks.daily_satellite_sync',
        'schedule': crontab(hour="2", minute="30"),  # Every day at 2:30 AM
    },
}