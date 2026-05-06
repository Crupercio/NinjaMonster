#!/bin/sh
python manage.py migrate --noinput
python manage.py createsuperuser --noinput || true
python manage.py seed_gen1 || true
python manage.py seed_pokeapi || true
python manage.py seed_move_pools || true
python manage.py seed_passives || true
python manage.py seed_stickers_all || true
python manage.py seed_album_pages || true
python manage.py seed_zones || true
python manage.py seed_quests || true
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
