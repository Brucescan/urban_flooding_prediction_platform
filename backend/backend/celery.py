# celery.py
from celery import Celery
from datetime import timedelta
import os
from django.core.cache import cache
from celery.schedules import crontab
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('webgis_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# 使用数据表存储首次运行标记
FIRST_RUN_KEY = 'celery_first_run_v2'

app.conf.beat_schedule = {
    'sync-sentinel2-weekly': {
        'task': 'data_pipeline.tasks.monthly_satellite_sync',
        'schedule': crontab(minute=0, hour=12, day_of_week=0),  # 每周日中午12点
        'options': {
            'expires': 3600 * 23,  # 23小时后过期
            'queue': 'satellite_sync'
        }
    }
}


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    """改进的初始化逻辑"""
    try:
        # 确保数据库连接可用
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        # 使用原子操作确保只执行一次
        from django.core.cache import caches
        persistent_cache = caches['persistent']

        if not persistent_cache.get(FIRST_RUN_KEY):
            # 使用双重检查锁模式
            with cache.lock('celery_init_lock', timeout=60):
                if not persistent_cache.get(FIRST_RUN_KEY):
                    sender.send_task(
                        'data_pipeline.tasks.monthly_satellite_sync',
                        queue='satellite_sync',
                        kwargs={'first_run': True}
                    )
                    persistent_cache.set(FIRST_RUN_KEY, True, timeout=None)
    except Exception as e:
        logger.error(f"Celery初始化失败: {str(e)}")
