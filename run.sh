#!/bin/bash
set -e

cd "$(dirname "$0")"

stop_server() {
    if lsof -ti:8000 >/dev/null 2>&1; then
        echo "Stopping Django server on port 8000..."
        kill $(lsof -ti:8000) 2>/dev/null || true
        sleep 1
    else
        echo "No Django server running on port 8000."
    fi
}

start_server() {
    echo "Starting Django server..."
    exec python3.11 manage.py runserver
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
