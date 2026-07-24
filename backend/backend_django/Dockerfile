FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 8000

CMD ["sh", "-c", \
    "python manage.py makemigrations api --noinput && \
     python manage.py migrate --noinput && \
     python seed.py && \
     gunicorn facturacion.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
