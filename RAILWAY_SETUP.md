# Railway Deployment Setup

## Quick Start

1. **Deploy on Railway:**
   - GitHub repo linked to Railway
   - Postgres service auto-created
   - Web service running Flask API

2. **Load Centerline Data (One-time)**

   After deployment is stable, load the centerline data manually:

   ```bash
   # Get your Postgres connection string from Railway dashboard:
   # Postgres service → Variables → DATABASE_URL
   
   export DATABASE_URL="postgresql://postgres:PASSWORD@postgres.railway.internal:5432/railway"
   
   # Load data
   uv run python holos_tools/load_centerlines.py
   ```

   Or use Railway CLI:
   ```bash
   railway run python holos_tools/load_centerlines.py
   ```

## Why Manual Loading?

Railway's managed Postgres crashes when loading 225MB of GeoJSON on startup. This is a resource constraint on the free tier. Manual loading gives Postgres time to stabilize first.

## API Endpoints

Once data is loaded:
- `GET /api/streets.geojson?bbox=minLon,minLat,maxLon,maxLat`
- `GET /api/curbs.geojson?bbox=minLon,minLat,maxLon,maxLat`
- `GET /health` — health check

## Troubleshooting

**Postgres keeps crashing:**
- Check Railway dashboard for Postgres logs
- Free tier has 100MB memory limit; GeoJSON loading needs 1GB+
- Consider upgrading Postgres plan or splitting data into smaller chunks

**API not responding:**
- Ensure DATABASE_URL is set in web service variables
- Check web service Deploy Logs for connection errors
