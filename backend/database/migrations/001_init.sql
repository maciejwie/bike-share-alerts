-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Stations Metadata
CREATE TABLE IF NOT EXISTS stations (
    station_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    capacity INTEGER NOT NULL,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Station Status History
CREATE TABLE IF NOT EXISTS station_status (
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

-- Convert to Hypertable (Idempotent check via PL/pgSQL block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'station_status'
    ) THEN
        PERFORM create_hypertable('station_status', 'time');
    END IF;
END
$$;

-- Index
CREATE INDEX IF NOT EXISTS idx_station_status_station_time ON station_status (station_id, time DESC);

-- Users
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_token TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Routes
CREATE TABLE IF NOT EXISTS routes (
    route_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    name TEXT NOT NULL,
    start_station_id TEXT REFERENCES stations(station_id),
    end_station_id TEXT REFERENCES stations(station_id),
    target_arrival_time TIME,
    alert_lead_time_minutes INTEGER DEFAULT 15,
    days_of_week INTEGER[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX IF NOT EXISTS idx_routes_active ON routes (is_active);
