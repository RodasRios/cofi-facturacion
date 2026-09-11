#!/bin/sh
set -e

# Aplica las migraciones que ya existen en el repo.
# OJO: aquí nunca se corre 'makemigrations'. Las migraciones se generan en
# desarrollo, se commitean como archivos 000N_*.py y aquí solo se aplican.
python manage.py migrate --noinput

# El seed (usuario admin + plantas + materiales de ejemplo) solo corre si se
# pide explícitamente. En producción se deja RUN_SEED=false una vez creados
# los datos reales, para no reinsertar las plantas/materiales de ejemplo.
if [ "${RUN_SEED:-true}" = "true" ]; then
    python seed.py
fi

exec gunicorn facturacion.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --access-logfile - \
    --error-logfile -
