FROM python:3.11-slim

# Устанавливаем системные зависимости для сборки mysqlclient
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Собираем статику
RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "secret_santa.wsgi:application", "--bind", "0.0.0.0:8000"]
