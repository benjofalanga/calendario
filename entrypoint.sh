#!/bin/sh
set -eu

PORT="${PORT:-8000}"
SQLITE_PATH="${SQLITE_PATH:-/app/db.sqlite3}"

mkdir -p "$(dirname "${SQLITE_PATH}")"
touch "${SQLITE_PATH}"

python manage.py migrate --noinput

exec python manage.py runserver "0.0.0.0:${PORT}"
