#!/bin/bash
set -e

cd "$(dirname "$0")"

stop_server() {
    if lsof -ti:8080 >/dev/null 2>&1; then
        echo "Stopping Django server on port 8080..."
        kill $(lsof -ti:8080) 2>/dev/null || true
        sleep 1
    else
        echo "No Django server running on port 8080."
    fi
}

start_server() {
    export PATH="/c/Program Files/PostgreSQL/18/bin:$PATH"

    echo "Checking database..."
    PGPASSWORD="Password09!" psql -U postgres -p 5008 -tc "SELECT 1 FROM pg_database WHERE datname = 'network';" | grep -q 1 || PGPASSWORD="Password09!" createdb -U postgres -p 5008 network 2>/dev/null || true

    echo "Running migrations..."
    python manage.py migrate

    echo "Seeding data..."
    python manage.py seed

    echo "Starting Django server..."
    exec python manage.py runserver 8080
}

ACTION="${1:-start}"

case "$ACTION" in
    stop)
        stop_server
        ;;
    start)
        start_server
        ;;
    restart)
        stop_server
        start_server
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
esac
