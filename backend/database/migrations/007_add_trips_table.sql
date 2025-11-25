-- Migration 007: Add trips table for tracking route monitoring sessions

-- Trips: Historical record of all route monitoring sessions
CREATE TABLE trips (
    trip_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route_id UUID NOT NULL REFERENCES routes(route_id) ON DELETE CASCADE,
    user_email TEXT NOT NULL REFERENCES users(user_email) ON DELETE CASCADE,

    -- State machine: STARTING -> CYCLING -> DOCKING -> COMPLETE
    state TEXT NOT NULL DEFAULT 'STARTING',

    -- State transition timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- STARTING state begins
    cycling_started_at TIMESTAMPTZ, -- CYCLING state begins (iOS /trip/start)
    docking_started_at TIMESTAMPTZ, -- DOCKING state begins (within 500m)
    completed_at TIMESTAMPTZ, -- COMPLETE (iOS /trip/end)

    -- Monitoring focus (for change detection alerts)
    last_checked_at TIMESTAMPTZ,
    focused_station_id INTEGER, -- Current station being monitored/alerted about
    last_bike_count INTEGER, -- For STARTING state change alerts
    last_dock_count INTEGER, -- For DOCKING state change alerts

    -- Location tracking (from iOS)
    last_known_lat DOUBLE PRECISION,
    last_known_lon DOUBLE PRECISION,
    last_location_update_at TIMESTAMPTZ,

    CONSTRAINT valid_trip_state CHECK (
        state IN ('STARTING', 'CYCLING', 'DOCKING', 'COMPLETE')
    )
);

-- Index for cron to find active trips needing monitoring
CREATE INDEX idx_trips_active_monitoring ON trips (state, last_checked_at)
    WHERE state IN ('STARTING', 'DOCKING') AND completed_at IS NULL;

-- Index for finding user's active trip
CREATE INDEX idx_trips_user_active ON trips (user_email, completed_at)
    WHERE completed_at IS NULL;

-- Index for historical analysis
CREATE INDEX idx_trips_completed ON trips (completed_at DESC) WHERE completed_at IS NOT NULL;
