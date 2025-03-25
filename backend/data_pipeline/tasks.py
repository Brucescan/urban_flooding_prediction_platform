from celery import shared_task
from django.core.management import call_command

@shared_task
def daily_satellite_sync():
    """Celery定时任务：每日同步卫星数据"""
    call_command('fetch_sentinel2')
    call_command('process_ndvi', '--input=/path/to/input', '--output=/path/to/output')