#!/bin/bash
# =============================================================================
# ArborWatch — Container Entrypoint Script
# =============================================================================
# Handles startup ordering:
#   1. Wait for database to be available
#   2. Run migrations
#   3. Collect static files
#   4. Execute the CMD (gunicorn, celery worker, etc.)
# =============================================================================

set -e

echo "========================================"
echo " ArborWatch — Starting up..."
echo "========================================"

# Wait for database
echo "[entrypoint] Waiting for database..."
python manage.py wait_for_db --timeout 60

# Run migrations
echo "[entrypoint] Applying database migrations..."
python manage.py migrate --noinput

# Collect static files (skip in worker/beat containers)
if [ "$SKIP_COLLECTSTATIC" != "true" ]; then
    echo "[entrypoint] Collecting static files..."
    python manage.py collectstatic --noinput --clear 2>/dev/null || true
fi

echo "[entrypoint] Startup complete. Executing command: $@"
echo "========================================"

# Execute the CMD
exec "$@"
