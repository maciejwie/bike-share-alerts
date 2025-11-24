-- Migration 005: Convert station IDs from TEXT to INTEGER arrays, add thresholds, and rename arrival to departure

-- This migration:
-- 1. Changes start_station_id and end_station_id from TEXT to INTEGER arrays
-- 2. Adds bikes_threshold and docks_threshold columns to routes
-- 3. Renames target_arrival_time to target_departure_time (it's when you leave, not arrive)

-- Step 1: Add new array columns
ALTER TABLE routes ADD COLUMN start_station_ids INTEGER[];
ALTER TABLE routes ADD COLUMN end_station_ids INTEGER[];

-- Step 2: Migrate existing data (convert TEXT to single-element INTEGER arrays)
UPDATE routes SET start_station_ids = ARRAY[start_station_id::INTEGER] WHERE start_station_id IS NOT NULL AND start_station_id != '';
UPDATE routes SET end_station_ids = ARRAY[end_station_id::INTEGER] WHERE end_station_id IS NOT NULL AND end_station_id != '';

-- Step 3: Drop old TEXT columns
ALTER TABLE routes DROP COLUMN start_station_id;
ALTER TABLE routes DROP COLUMN end_station_id;

-- Step 4: Add threshold columns with sensible defaults
ALTER TABLE routes ADD COLUMN bikes_threshold INTEGER DEFAULT 2;
ALTER TABLE routes ADD COLUMN docks_threshold INTEGER DEFAULT 2;

-- Step 5: Set NOT NULL after adding defaults
ALTER TABLE routes ALTER COLUMN bikes_threshold SET NOT NULL;
ALTER TABLE routes ALTER COLUMN docks_threshold SET NOT NULL;

-- Step 6: Rename target_arrival_time to target_departure_time
ALTER TABLE routes RENAME COLUMN target_arrival_time TO target_departure_time;
