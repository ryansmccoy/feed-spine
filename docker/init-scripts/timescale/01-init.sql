-- FeedSpine TimescaleDB Initialization Script
-- This runs automatically on first container start

-- Create extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schema
CREATE SCHEMA IF NOT EXISTS feedspine;

-- Grant permissions
GRANT ALL ON SCHEMA feedspine TO feedspine;

-- Set default schema
ALTER DATABASE feedspine SET search_path TO feedspine, public;

-- Log that initialization is complete
DO $$
BEGIN
    RAISE NOTICE 'FeedSpine TimescaleDB initialization complete';
END $$;
