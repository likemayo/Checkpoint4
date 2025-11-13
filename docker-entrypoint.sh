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
    echo "Checking if database needs seeding..."
    
    # Check if users already exist (using Python to query database)
    USER_COUNT=$(python -c "
import sqlite3
import os
db_path = os.environ.get('APP_DB_PATH', '/app/data/app.sqlite')
try:
    conn = sqlite3.connect(db_path)
    count = conn.execute('SELECT COUNT(*) FROM user').fetchone()[0]
    conn.close()
    print(count)
except:
    print(0)
" 2>/dev/null || echo "0")
    
    if [ "$USER_COUNT" -eq "0" ]; then
        echo "Database is empty. Seeding initial data..."
        python -m src.seed || echo "Note: Seed data may already exist"
        python -m db.seed_flash_sales || echo "Note: Flash sales seed data may already exist"
        echo "✓ Database seeded successfully!"
    else
        echo "✓ Database already has $USER_COUNT users. Skipping seed (preserving existing data)."
    fi
else
    echo "Skipping database seeding (SEED_DATA not set to true)"
fi

# Start the Flask application
echo "Starting Flask application on port ${PORT:-5000}..."
exec python -m flask --app src.app:create_app run --host=0.0.0.0 --port="${PORT:-5000}"
