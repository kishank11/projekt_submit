-- 001_staging.sql
-- Staging area for the reusable ingestion core.
-- Requires PostgreSQL 16+ and PostGIS 3.4+.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.source_record (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    country_code char(2)     NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
    region_code  text                 CHECK (region_code IS NULL OR region_code ~ '^[A-Z0-9]{1,3}$'),
    source_id    text        NOT NULL CHECK (source_id <> ''),
    record_key   text        NOT NULL CHECK (record_key <> ''),
    source_date  date        NOT NULL,
    fetched_at   timestamptz NOT NULL,
    attributes   jsonb       NOT NULL DEFAULT '{}'::jsonb,
    geom         geometry(Geometry, 4326),
    batch_id     uuid        NOT NULL,
    loaded_at    timestamptz NOT NULL DEFAULT now(),
    -- identity is always country scoped
    CONSTRAINT source_record_identity UNIQUE (country_code, source_id, record_key),
    CONSTRAINT source_record_geom_valid CHECK (geom IS NULL OR ST_IsValid(geom))
);

CREATE INDEX IF NOT EXISTS source_record_geom_gix
    ON staging.source_record USING gist (geom);
CREATE INDEX IF NOT EXISTS source_record_country_source_idx
    ON staging.source_record (country_code, source_id);

CREATE TABLE IF NOT EXISTS staging.rejected_record (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id   text        NOT NULL,
    record_key  text        NOT NULL,
    reasons     text[]      NOT NULL,
    raw         jsonb       NOT NULL,
    batch_id    uuid        NOT NULL,
    rejected_at timestamptz NOT NULL DEFAULT now()
);
