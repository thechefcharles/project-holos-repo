"""Database utilities for PostGIS hub."""

import json
import logging
from typing import Any, Optional

import geopandas as gpd
import psycopg
import sqlalchemy as sa
from geopandas import GeoDataFrame
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class HolosDB:
    """PostGIS hub connection and utilities."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine: Optional[Engine] = None

    def connect(self) -> Engine:
        """Create or return SQLAlchemy engine."""
        if self.engine is None:
            # Use psycopg3 driver (postgresql+psycopg://)
            db_url = self.db_url.replace('postgresql://', 'postgresql+psycopg://')
            self.engine = sa.create_engine(db_url, poolclass=NullPool)
        return self.engine

    def execute(self, sql: str, params: Optional[dict] = None) -> list[dict]:
        """Execute raw SQL and return results as list of dicts."""
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or {})
                if cur.description:
                    cols = [d[0] for d in cur.description]
                    return [dict(zip(cols, row)) for row in cur.fetchall()]
        return []

    def load_geodataframe(
        self,
        gdf: GeoDataFrame,
        table_name: str,
        schema: str = "staging",
        if_exists: str = "append",
    ) -> None:
        """Load GeoDataFrame to PostGIS using GeoAlchemy2."""
        engine = self.connect()
        gdf.to_postgis(table_name, engine, schema=schema, if_exists=if_exists, index=False)
        logger.info(f"Loaded {len(gdf)} rows to {schema}.{table_name}")

    def read_query(self, sql: str, params: Optional[dict] = None) -> GeoDataFrame:
        """Execute SQL and return as GeoDataFrame (if geometry column present)."""
        engine = self.connect()
        gdf = gpd.read_postgis(sql, engine, params=params)
        return gdf

    def table_exists(self, table_name: str, schema: str = "public") -> bool:
        """Check if table exists."""
        engine = self.connect()
        inspector = sa.inspect(engine)
        return inspector.has_table(table_name, schema=schema)

    def truncate(self, table_name: str, schema: str = "public", cascade: bool = False) -> None:
        """Truncate table."""
        engine = self.connect()
        cascade_str = "CASCADE" if cascade else ""
        with engine.begin() as conn:
            conn.exec_driver_sql(f"TRUNCATE {schema}.{table_name} {cascade_str}")
        logger.info(f"Truncated {schema}.{table_name}")


def insert_source_record(db: HolosDB, source_id: str, kind: str, url: str, rights: str) -> None:
    """Insert a source record into ops.sources."""
    sql = """
    INSERT INTO ops.sources (source_id, kind, url, rights, retrieved_at, checksum, manifest)
    VALUES (%(source_id)s, %(kind)s, %(url)s, %(rights)s, now(), '', %(manifest)s)
    ON CONFLICT (source_id) DO NOTHING
    """
    db.execute(
        sql,
        {
            "source_id": source_id,
            "kind": kind,
            "url": url,
            "rights": rights,
            "manifest": json.dumps({"url": url}),
        },
    )
    logger.info(f"Inserted source record: {source_id}")
