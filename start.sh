#!/bin/sh
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
