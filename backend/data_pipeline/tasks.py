from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
import fasteners
from pathlib import Path


@shared_task(bind=True)
def monthly_satellite_sync(self, first_run=False):
    """卫星数据同步任务"""

    # 分布式文件锁（防止多实例同时运行）
    lock_path = Path('/tmp/satellite_sync.lock')
    lock = fasteners.InterProcessLock(str(lock_path))

    if not lock.acquire(blocking=False):
        return "Another sync is already running"

    try:
        # 如果不是首次强制运行，则检查冷却期
        if not first_run:
            last_run = cache.get('last_sync_time')
            if last_run and (timezone.now() - last_run).total_seconds() < 604700:  # 7天-100秒缓冲
                return f"Skip: Last run at {last_run.strftime('%Y-%m-%d %H:%M')}"

        # 执行核心逻辑
        from django.core.management import call_command
        call_command('fetch_sentinel2')

        # 记录成功执行时间（永久存储）
        cache.set('last_sync_time', timezone.now(), timeout=None)
        return "Sync completed successfully"

    except Exception as e:
        # 指数退避重试（最多3次）
        countdown = min(60 * (2 ** self.request.retries), 3600)
        raise self.retry(exc=e, countdown=countdown, max_retries=3)
    finally:
        lock.release()
