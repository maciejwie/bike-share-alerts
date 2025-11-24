-- Migration 004: Schema updates - changing user schema

-- This is a breaking change that requires recreating several tables
-- All existing user, key and route data will be lost

-- Step 1: Drop dependent tables (cascade will handle this)
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS routes CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Step 2: Create new users table with email as primary key
CREATE TABLE users (
    user_email TEXT PRIMARY KEY,
    user_firstname TEXT,
    user_lastname TEXT,
    device_token TEXT, -- For APNs
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 3: Recreate routes table with user_email foreign key and INTEGER station_id
CREATE TABLE routes (
    route_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_email TEXT NOT NULL REFERENCES users(user_email) ON DELETE CASCADE,
    name TEXT NOT NULL,
    start_station_id INTEGER REFERENCES stations(station_id),
    end_station_id INTEGER REFERENCES stations(station_id),
    target_arrival_time TIME,
    alert_lead_time_minutes INTEGER DEFAULT 15,
    days_of_week INTEGER[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_routes_active ON routes (is_active);

-- Step 4: Recreate api_keys table with user_email foreign key and unique constraint
CREATE TABLE api_keys (
    key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_email TEXT NOT NULL REFERENCES users(user_email) ON DELETE CASCADE,
    key_value TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    CONSTRAINT unique_user_key_label UNIQUE (user_email, label)
);

CREATE INDEX idx_api_keys_value ON api_keys(key_value);
CREATE INDEX idx_api_keys_user_email ON api_keys(user_email);
