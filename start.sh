#!/bin/sh
python manage.py migrate --noinput
python manage.py createsuperuser --noinput || true
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
