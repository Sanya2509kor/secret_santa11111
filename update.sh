#!/bin/bash
echo "Обновление сайта..."
git pull origin main
docker compose up -d --build
docker compose exec -T web python manage.py migrate
docker compose exec -T web python manage.py collectstatic --noinput
echo "Готово!"
