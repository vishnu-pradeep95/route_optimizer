-- =============================================================================
-- Kerala LPG Delivery Route Optimizer — Database Schema
-- =============================================================================
-- Runs once on first 'docker compose up' via Docker entrypoint.
-- PostGIS extension provides spatial types (geometry, geography) and
-- spatial indexes (GiST) for GPS coordinate queries.
--
-- SRID 4326 = WGS84 (standard GPS coordinate system, used worldwide)
-- =============================================================================

-- Enable PostGIS for spatial data types and functions.
-- PostGIS turns PostgreSQL into a Geographic Information System (GIS).
-- It adds SQL types like geometry(Point, 4326) and functions like
-- ST_Distance(), ST_DWithin(), ST_MakePoint().
-- Without PostGIS, you'd store lat/lon as plain floats and lose the ability
-- to do efficient spatial queries ("find all orders within 2 km").
-- See: https://postgis.net/docs/
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable uuid-ossp for server-side UUID generation.
-- UUID primary keys are better than auto-increment integers for distributed
-- systems: they're globally unique, so you can merge data from different
-- sources without ID collisions. uuid_generate_v4() creates random UUIDs.
-- Trade-off: UUIDs are 16 bytes vs 4 bytes for int, slightly slower to index.
-- At our scale (~50 orders/day), the difference is negligible.
-- See: https://www.postgresql.org/docs/current/uuid-ossp.html
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- VEHICLES — delivery fleet (Piaggio Ape Xtra LDX three-wheelers)
-- =============================================================================
-- Why a table instead of config.py?
-- In Phase 2+, vehicles may have different specs (diesel vs electric),
-- different depots, and maintenance schedules. A table supports this
-- growth without code changes.
CREATE TABLE IF NOT EXISTS vehicles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id      VARCHAR(20) UNIQUE NOT NULL,   -- e.g. "VEH-01"
    registration_no VARCHAR(20),                    -- e.g. "KL-07-XX-1234"
    vehicle_type    VARCHAR(30) DEFAULT 'diesel',   -- diesel, cng, electric
    max_weight_kg   REAL NOT NULL DEFAULT 446.0,    -- 90% of rated payload
    max_items       INTEGER NOT NULL DEFAULT 30,
    depot_location  geometry(Point, 4326) NOT NULL, -- PostGIS point (lon, lat)
    speed_limit_kmh REAL DEFAULT 40.0,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- DRIVERS — standalone driver entities (not linked to vehicles)
-- =============================================================================
-- Phase 16: Drivers are standalone entities. name_normalized stores the
-- uppercase, trimmed, collapsed-space version of the name for fuzzy matching.
-- No phone or vehicle_id — drivers are matched to routes via driver_id on routes.
CREATE TABLE IF NOT EXISTS drivers (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name             VARCHAR(100) NOT NULL,
    name_normalized  VARCHAR(100) NOT NULL,           -- UPPER(TRIM(name)), for fuzzy matching
    is_active        BOOLEAN DEFAULT true,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast name lookups during fuzzy matching
CREATE INDEX IF NOT EXISTS idx_drivers_name_normalized ON drivers(name_normalized);
-- Unique constraint prevents exact duplicate names at DB level
CREATE UNIQUE INDEX IF NOT EXISTS idx_drivers_name_normalized_unique ON drivers(name_normalized);

-- =============================================================================
-- OPTIMIZATION RUNS — one row per optimizer invocation
-- =============================================================================
-- Every time someone uploads a CSV and triggers optimization, we create a run.
-- This provides an audit trail and lets us compare optimization results over time.
CREATE TABLE IF NOT EXISTS optimization_runs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    total_orders        INTEGER NOT NULL,
    orders_assigned     INTEGER NOT NULL DEFAULT 0,
    orders_unassigned   INTEGER NOT NULL DEFAULT 0,
    vehicles_used       INTEGER NOT NULL DEFAULT 0,
    optimization_time_ms REAL,
    safety_multiplier   REAL NOT NULL DEFAULT 1.3,
    -- Which CSV file was uploaded (filename, not contents — privacy)
    source_filename     VARCHAR(255),
    status              VARCHAR(20) DEFAULT 'completed',  -- completed, failed, in_progress
    notes               TEXT
);

-- =============================================================================
-- ORDERS — delivery orders from CDCMS CSV import
-- =============================================================================
-- One row per delivery order. Linked to an optimization run.
-- Coordinates stored as PostGIS geometry for spatial queries.
CREATE TABLE IF NOT EXISTS orders (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id              UUID NOT NULL REFERENCES optimization_runs(id) ON DELETE CASCADE,
    order_id            VARCHAR(50) NOT NULL,           -- from CSV: "ORD-001"
    customer_ref        VARCHAR(50),                    -- pseudonymized customer ID
    address_raw         TEXT,                           -- raw address text from CSV
    address_display     VARCHAR(255),                   -- cleaned address for driver
    address_original    TEXT,                           -- completely unprocessed CDCMS text
    location            geometry(Point, 4326),          -- PostGIS point (lon, lat)
    weight_kg           REAL NOT NULL,
    quantity            INTEGER NOT NULL DEFAULT 1,
    cylinder_type       VARCHAR(30),                    -- domestic, commercial, 5kg
    priority            INTEGER NOT NULL DEFAULT 2,     -- 1=high, 2=normal, 3=low
    service_time_min    REAL DEFAULT 5.0,               -- minutes at stop
    delivery_window_start TIME,                         -- Phase 2: time window support
    delivery_window_end   TIME,                         -- Phase 2: time window support
    notes               TEXT,
    status              VARCHAR(20) DEFAULT 'pending',  -- pending, assigned, delivered, failed
    geocode_confidence  REAL,                           -- 0.0-1.0 from geocoder
    geocode_method      VARCHAR(20),                    -- direct, area_retry, centroid, depot
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Spatial index on order locations for proximity queries.
-- GiST (Generalized Search Tree) is PostGIS's spatial index type.
-- It organizes geometry data in a tree structure that supports operators
-- like && (bounding box overlap) and <-> (distance). Without this index,
-- a query like "find orders within 2 km" would scan every row.
-- With the index, PostgreSQL can quickly eliminate distant points.
CREATE INDEX IF NOT EXISTS idx_orders_location ON orders USING gist(location);
-- Fast lookup by optimization run (B-tree: standard for equality/range queries)
CREATE INDEX IF NOT EXISTS idx_orders_run_id ON orders(run_id);

-- =============================================================================
-- ROUTES — optimized routes (one per vehicle per optimization run)
-- =============================================================================
CREATE TABLE IF NOT EXISTS routes (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id                  UUID NOT NULL REFERENCES optimization_runs(id) ON DELETE CASCADE,
    vehicle_id              VARCHAR(20) NOT NULL,       -- "VEH-01"
    driver_name             VARCHAR(100),
    driver_id               UUID REFERENCES drivers(id),  -- Phase 16: FK to standalone drivers table
    total_distance_km       REAL DEFAULT 0.0,
    total_duration_minutes  REAL DEFAULT 0.0,
    total_weight_kg         REAL DEFAULT 0.0,
    total_items             INTEGER DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_routes_run_id ON routes(run_id);

-- =============================================================================
-- ROUTE_STOPS — ordered stops within a route
-- =============================================================================
CREATE TABLE IF NOT EXISTS route_stops (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id                    UUID NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    order_id                    UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sequence                    INTEGER NOT NULL,           -- 1-based stop order
    location                    geometry(Point, 4326),
    address_display             VARCHAR(255),
    address_original            TEXT,
    distance_from_prev_km       REAL DEFAULT 0.0,
    duration_from_prev_minutes  REAL DEFAULT 0.0,
    weight_kg                   REAL DEFAULT 0.0,
    quantity                    INTEGER DEFAULT 1,
    notes                       TEXT,
    status                      VARCHAR(20) DEFAULT 'pending',  -- pending, en_route, delivered, failed
    delivered_at                TIMESTAMPTZ,                     -- when driver tapped "delivered"
    delivery_location           geometry(Point, 4326),          -- GPS at delivery time (driver-verified)
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_route_stops_route_id ON route_stops(route_id);

-- =============================================================================
-- TELEMETRY — GPS pings from driver apps (Phase 2+)
-- =============================================================================
-- High-volume table: one row per GPS ping per driver.
-- At 30-second intervals × 13 drivers × 16-hour day = ~25,000 rows/day.
-- That's ~750,000 rows/month. After 6 months, you'll have ~4.5M rows.
--
-- Performance note: at this scale, standard PostgreSQL handles it fine.
-- If you later have 100+ drivers or 5-second ping intervals, consider:
-- - TimescaleDB hypertable: auto-partitions by time, faster range queries
-- - Monthly table partitioning: CREATE TABLE telemetry_2026_02 PARTITION OF ...
-- For now, the indexes below are sufficient.
CREATE TABLE IF NOT EXISTS telemetry (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id  VARCHAR(20) NOT NULL,
    driver_name VARCHAR(100),
    location    geometry(Point, 4326) NOT NULL,
    speed_kmh   REAL,                           -- from GPS or computed
    accuracy_m  REAL,                           -- GPS accuracy in meters
    heading     REAL,                           -- degrees 0-360
    recorded_at TIMESTAMPTZ NOT NULL,           -- when the GPS reading was taken
    received_at TIMESTAMPTZ DEFAULT NOW(),      -- when the server got it
    -- Flag speed violations for safety review
    speed_alert BOOLEAN DEFAULT false           -- true if speed > 40 km/h urban
);

-- Spatial index for "where are all drivers now?" queries.
-- Uses GiST because the column is a PostGIS geometry type.
CREATE INDEX IF NOT EXISTS idx_telemetry_location ON telemetry USING gist(location);
-- Time-based index for recent telemetry lookups.
-- DESC ordering: newest pings first (most common query pattern).
CREATE INDEX IF NOT EXISTS idx_telemetry_recorded_at ON telemetry(recorded_at DESC);
-- Composite index: vehicle + time for "show me this driver's trace today".
-- This is the most-used telemetry query pattern. The composite index
-- lets PostgreSQL find all pings for VEH-01 in the last hour with a
-- single index scan (vs scanning all vehicles then filtering).
CREATE INDEX IF NOT EXISTS idx_telemetry_vehicle_time ON telemetry(vehicle_id, recorded_at DESC);

-- =============================================================================
-- GEOCODE_CACHE — reusable address→coordinate mappings
-- =============================================================================
-- Every successful geocoding result is cached here. Repeat customers
-- get free geocoding. Over time this becomes more valuable than any API.
-- Driver-verified coordinates (from delivery GPS) are the gold standard.
--
-- Cost savings example: Google Maps Geocoding API costs $5 per 1,000 requests.
-- With 50 deliveries/day and 60% repeat customers, caching saves:
--   30 cached lookups/day × 30 days = 900 free lookups/month = ~$4.50/month
-- After 6 months of operation, 80%+ of addresses are cached → almost free.
--
-- The UNIQUE(address_norm, source) constraint prevents duplicate entries:
-- if Google and a driver both geocode "MG Road, Kochi", we keep both
-- (different sources may have different confidence levels).
CREATE TABLE IF NOT EXISTS geocode_cache (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    address_raw     TEXT NOT NULL,
    address_norm    TEXT NOT NULL,                   -- normalized/lowercased for matching
    location        geometry(Point, 4326) NOT NULL,
    source          VARCHAR(30) NOT NULL,            -- 'google', 'driver_verified', 'manual'
    confidence      REAL DEFAULT 0.0,                -- 0.0-1.0
    hit_count       INTEGER DEFAULT 1,               -- how many times this was reused
    last_used_at    TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(address_norm, source)
);

CREATE INDEX IF NOT EXISTS idx_geocode_cache_address ON geocode_cache(address_norm);
CREATE INDEX IF NOT EXISTS idx_geocode_cache_location ON geocode_cache USING gist(location);

-- =============================================================================
-- Seed data
-- =============================================================================
-- Phase 16 (DRV-07): No pre-loaded fleet or driver data.
-- Vehicles and drivers are created via the dashboard or CSV upload.
-- Fresh database starts with zero vehicles and zero drivers.
