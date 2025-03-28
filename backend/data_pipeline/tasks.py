from celery import shared_task
from django.core.cache import cache
from django.utils import timezone


@shared_task(bind=True)
def monthly_satellite_sync(self):
    # 检查是否在冷却期（7天内）
    last_run = cache.get('last_sync_time')
    if last_run and (timezone.now() - last_run).days < 7:
        return f"Skip: Last run at {last_run} (cooling down)"

    try:
        # 调用你的管理命令
        from django.core.management import call_command
        call_command('fetch_sentinel2')

        # 记录成功执行时间
        cache.set('last_sync_time', timezone.now())
        return "Task executed successfully"
    except Exception as e:
        self.retry(exc=e, countdown=60)  # 失败后重试