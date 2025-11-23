-- Reset (Optional, use with caution in production)
DROP TABLE IF EXISTS routes CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS station_status CASCADE;
DROP TABLE IF EXISTS stations CASCADE;

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Stations Metadata (Relatively static)
CREATE TABLE stations (
    station_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    capacity INTEGER NOT NULL,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Station Status History (Hypertable)
CREATE TABLE station_status (
    time TIMESTAMPTZ NOT NULL,
    station_id TEXT NOT NULL,
    num_bikes_available INTEGER NOT NULL,
    num_ebikes_available INTEGER DEFAULT 0,
    num_docks_available INTEGER NOT NULL,
    is_installed BOOLEAN DEFAULT TRUE,
    is_renting BOOLEAN DEFAULT TRUE,
    is_returning BOOLEAN DEFAULT TRUE,
    CONSTRAINT fk_station
        FOREIGN KEY(station_id) 
        REFERENCES stations(station_id)
);

-- Convert to Hypertable partitioned by time
SELECT create_hypertable('station_status', 'time');

-- Create index for querying specific station history efficiently
CREATE INDEX idx_station_status_station_time ON station_status (station_id, time DESC);

-- Users (Simple for MVP, identified by device UUID or token)
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_token TEXT, -- For APNs or identification
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Routes Configuration
CREATE TABLE routes (
    route_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    name TEXT NOT NULL, -- e.g., "Commute to Work"
    start_station_id TEXT REFERENCES stations(station_id),
    end_station_id TEXT REFERENCES stations(station_id),
    target_arrival_time TIME, -- e.g., '08:30'
    alert_lead_time_minutes INTEGER DEFAULT 15, -- Alert 15 mins before
    days_of_week INTEGER[], -- Array of days (0=Sun, 1=Mon, etc.)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for finding active routes to monitor
CREATE INDEX idx_routes_active ON routes (is_active);

-- Current Station Status (Snapshot for efficient deduplication)
CREATE TABLE IF NOT EXISTS current_station_status (
    station_id TEXT PRIMARY KEY,
    num_bikes_available INTEGER NOT NULL,
    num_ebikes_available INTEGER DEFAULT 0,
    num_docks_available INTEGER NOT NULL,
    is_installed BOOLEAN DEFAULT TRUE,
    is_renting BOOLEAN DEFAULT TRUE,
    is_returning BOOLEAN DEFAULT TRUE,
    last_updated TIMESTAMPTZ NOT NULL
);
