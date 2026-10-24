FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем ВЕСЬ проект (корень /opt/santa_test)
COPY . .

# Устанавливаем зависимости (requirements.txt лежит в корне проекта)
RUN pip install --no-cache-dir -r requirements.txt

# Переходим в папку бота и запускаем его
WORKDIR /app/santa_bot
CMD ["python", "main.py"]
