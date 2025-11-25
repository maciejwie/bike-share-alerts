-- Migration 008: Convert station_id from TEXT to INTEGER in current_station_status table
-- This migration was missed in 006_convert_stations_to_integer.sql

-- Convert current_station_status.station_id from TEXT to INTEGER
ALTER TABLE current_station_status ALTER COLUMN station_id TYPE INTEGER USING station_id::INTEGER;
