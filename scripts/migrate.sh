#!/bin/bash
set -e

echo "Running Alembic migrations..."
python -m alembic upgrade head
echo "Migrations completed."
