#!/bin/sh

# 等待 PostgreSQL 启动
until PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -c '\q'; do
  >&2 echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

>&2 echo "PostgreSQL is up - executing migrations and starting server"

# 运行 Django 迁移
/opt/rgee-venv/bin/python manage.py migrate
/opt/rgee-venv/bin/python manage.py makemigrations
/opt/rgee-venv/bin/python manage.py makemigrations geodata
echo "Checking for existing superuser..."
if ! /opt/rgee-venv/bin/python manage.py createsuperuser --noinput \
    --username "$DJANGO_SUPERUSER_USERNAME" \
    --email "$DJANGO_SUPERUSER_EMAIL"; then
    echo "Superuser already exists."
else
    # 设置超级用户的密码
    /opt/rgee-venv/bin/python manage.py changepassword $DJANGO_SUPERUSER_USERNAME <<EOF
$DJANGO_SUPERUSER_PASSWORD
$DJANGO_SUPERUSER_PASSWORD
EOF
fi

# 运行 Django 开发服务器
exec /opt/rgee-venv/bin/python manage.py runserver 0.0.0.0:8000