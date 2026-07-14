#!/bin/bash
# Railway post-deployment script to load centerlines into PostgreSQL

set -e

echo "📍 Loading centerlines into PostgreSQL..."

# Wait for database to be ready
python -c "
import time
import psycopg
from holos_tools.core import Config

config = Config()
for attempt in range(30):
    try:
        with psycopg.connect(config.db_url) as conn:
            print('✓ Database ready')
            break
    except Exception as e:
        print(f'Waiting for database... ({attempt+1}/30)')
        time.sleep(1)
"

# Load centerlines
python holos_tools/load_centerlines.py

echo "✓ Deployment complete! API ready at $RAILWAY_PUBLIC_DOMAIN"
