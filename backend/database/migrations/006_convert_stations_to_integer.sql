-- Migration 006: Convert station_id from TEXT to INTEGER in stations and station_status tables

-- This migration changes station_id from TEXT to INTEGER across all tables
-- This is required to match the INTEGER[] arrays used in routes

-- Step 1: Drop the foreign key constraint from station_status
ALTER TABLE station_status DROP CONSTRAINT fk_station;

-- Step 2: Convert station_status.station_id from TEXT to INTEGER
ALTER TABLE station_status ALTER COLUMN station_id TYPE INTEGER USING station_id::INTEGER;

-- Step 3: Convert stations.station_id from TEXT to INTEGER
ALTER TABLE stations ALTER COLUMN station_id TYPE INTEGER USING station_id::INTEGER;

-- Step 4: Re-add the foreign key constraint
ALTER TABLE station_status ADD CONSTRAINT fk_station
    FOREIGN KEY(station_id)
    REFERENCES stations(station_id);
