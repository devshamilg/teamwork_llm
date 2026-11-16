#!/bin/sh
set -e

# If starting the web server, run Alembic migrations first
if [ "$1" = "uvicorn" ]; then
    echo "Running database migrations..."
    alembic upgrade head
    echo "Database migrations complete."
fi

exec "$@"
