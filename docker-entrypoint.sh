#!/bin/sh
# Docker entrypoint script for Checkpoint3 application

set -e

echo "Starting Checkpoint3 application..."

# Initialize database
echo "Initializing database..."
python -m src.main

# Run migrations
echo "Running database migrations..."
python scripts/run_migrations.py || echo "Note: Migrations may have already been applied"

# Seed initial data if needed (optional)
if [ "$SEED_DATA" = "true" ]; then
    echo "Seeding database..."
    python -m src.seed || echo "Note: Seed data may already exist"
    python -m db.seed_flash_sales || echo "Note: Flash sales seed data may already exist"
fi

# Start the Flask application
echo "Starting Flask application on port ${PORT:-5000}..."
exec python -m flask --app src.app:create_app run --host=0.0.0.0 --port="${PORT:-5000}"
