from celery import Celery
from datetime import timedelta
import os
from django.core.cache import cache

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('webgis_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# 每7天执行一次的配置
app.conf.beat_schedule = {
    'sync-sentinel2-weekly': {
        'task': 'data_pipeline.tasks.monthly_satellite_sync',
        'schedule': timedelta(days=7),  # 精确7天间隔
        'options': {'expires': 3600 * 24}  # 任务24小时后过期
    }
}

# 容器启动时立即执行（通过信号量）
@app.on_after_configure.connect
def trigger_first_run(sender, **kwargs):
    # 通过缓存标记防止重复立即执行
    if not cache.get('celery_first_run'):
        sender.send_task('data_pipeline.tasks.monthly_satellite_sync')
        cache.set('celery_first_run', True, timeout=None)  # 永久标记