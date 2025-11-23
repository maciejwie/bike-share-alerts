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
