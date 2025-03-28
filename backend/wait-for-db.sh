#!/bin/sh

set -e  # 任何命令失败时退出脚本

# 等待 PostgreSQL 启动（最多尝试 60 次）
MAX_RETRIES=60
retries=0
# 在脚本中修改这一行
until PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB -c '\q'; do
  retries=$((retries + 1))
  if [ $retries -ge $MAX_RETRIES ]; then
    >&2 echo "PostgreSQL is still unavailable after $MAX_RETRIES attempts - aborting"
    exit 1
  fi
  >&2 echo "PostgreSQL is unavailable (attempt $retries/$MAX_RETRIES) - sleeping"
  sleep 1
done

>&2 echo "PostgreSQL is up - applying database migrations"

# 运行 Django 迁移（跳过 makemigrations，生产环境应由 CI/CD 处理）
/opt/rgee-venv/bin/python manage.py migrate

# 检查并创建超级用户（安全方式）
>&2 echo "Checking for superuser: $DJANGO_SUPERUSER_USERNAME"
if /opt/rgee-venv/bin/python manage.py shell -c "\
from django.contrib.auth import get_user_model; \
User = get_user_model(); \
print(User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists())" | grep -q "False"; then
  >&2 echo "Creating superuser..."
  /opt/rgee-venv/bin/python manage.py createsuperuser \
    --username "$DJANGO_SUPERUSER_USERNAME" \
    --email "$DJANGO_SUPERUSER_EMAIL" \
    --noinput

  # 使用 Django 环境直接设置密码（避免命令行泄露）
  /opt/rgee-venv/bin/python manage.py shell -c "\
from django.contrib.auth import get_user_model; \
User = get_user_model(); \
user = User.objects.get(username='$DJANGO_SUPERUSER_USERNAME'); \
user.set_password('$DJANGO_SUPERUSER_PASSWORD'); \
user.save()"
  >&2 echo "Superuser created"
else
  >&2 echo "Superuser already exists - skipping"
fi

# 启动服务器
>&2 echo "Starting Django server"
exec /opt/rgee-venv/bin/python manage.py runserver 0.0.0.0:8000