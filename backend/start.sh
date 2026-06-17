#!/usr/bin/env bash

# Ensure we're in the correct directory
cd "$(dirname "$0")"

cmd_start() {
    # Create .env from example if it doesn't exist
    if [ ! -f .env ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "WARNING: Please update the .env file with your actual GEMINI_API_KEY."
    fi

    echo "Starting backend container..."
    docker compose up -d --build
    echo "Backend is starting on port 8080!"
}

cmd_stop() {
    echo "Stopping backend container..."
    docker compose down
    echo "Backend stopped."
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_logs() {
    docker compose logs -f
}

cmd_status() {
    docker compose ps
}

cmd_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start      Start the backend container (default)"
    echo "  stop       Stop the backend container"
    echo "  restart    Restart the backend container"
    echo "  logs       View the container logs"
    echo "  status     View container status"
    echo "  help       Show this help message"
}

cmd="${1:-start}"

case "$cmd" in
    start)    cmd_start ;;
    stop)     cmd_stop ;;
    restart)  cmd_restart ;;
    logs)     cmd_logs ;;
    status)   cmd_status ;;
    help|-h)  cmd_help ;;
    *)        echo "Unknown command: $cmd"; cmd_help; exit 1 ;;
esac
