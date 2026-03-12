"""SQLAlchemy ORM models — mirror the PostgreSQL schema in infra/postgres/init.sql.

These declarative models map Python classes to database tables. They use
SQLAlchemy 2.0's `mapped_column()` style for type-safe column definitions
with full IDE autocomplete.

Why duplicate the schema here instead of generating from SQL?
- Python-side validation (e.g., default values, type conversion)
- ORM relationships for convenient eager/lazy loading
- Alembic can auto-generate migrations by comparing these models to the DB
- IDE autocomplete on column names and types
The SQL file is the "source of truth" for initial schema creation;
these ORM models are the "source of truth" for application-level access.

PostGIS columns use GeoAlchemy2's Geometry type, which maps to
PostgreSQL's geometry(Point, 4326) and supports spatial queries.
See: https://geoalchemy-2.readthedocs.io/en/latest/
"""

import uuid
from datetime import datetime, time

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base class for all ORM models
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    Why a custom base instead of using declarative_base()?
    SQLAlchemy 2.0 recommends subclassing DeclarativeBase for:
    - Better type checking support (mapped_column types propagate)
    - Cleaner integration with Alembic
    See: https://docs.sqlalchemy.org/en/20/orm/mapping_api.html#sqlalchemy.orm.DeclarativeBase
    """

    pass


# ---------------------------------------------------------------------------
# VEHICLES
# ---------------------------------------------------------------------------
class VehicleDB(Base):
    """ORM model for the vehicles table.

    Represents a delivery vehicle in the fleet. For Kerala, these are
    Piaggio Ape Xtra LDX three-wheelers with ~446 kg payload capacity.

    Named 'VehicleDB' to distinguish from the Pydantic Vehicle model
    in core/models/vehicle.py. The Pydantic model is the API-facing DTO;
    this is the persistence layer.
    """

    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    registration_no: Mapped[str | None] = mapped_column(String(20))
    vehicle_type: Mapped[str] = mapped_column(String(30), default="diesel")
    max_weight_kg: Mapped[float] = mapped_column(Float, nullable=False, default=446.0)
    max_items: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # PostGIS Point column: stores (longitude, latitude) in SRID 4326 (WGS84)
    # GeoAlchemy2 handles WKB↔Python conversion automatically.
    depot_location = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    speed_limit_kmh: Mapped[float | None] = mapped_column(Float, default=40.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    drivers: Mapped[list["DriverDB"]] = relationship(back_populates="vehicle")


# ---------------------------------------------------------------------------
# DRIVERS
# ---------------------------------------------------------------------------
class DriverDB(Base):
    """ORM model for the drivers table.

    Links a driver to their currently assigned vehicle.
    """

    __tablename__ = "drivers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    vehicle: Mapped[VehicleDB | None] = relationship(back_populates="drivers")


# ---------------------------------------------------------------------------
# OPTIMIZATION RUNS
# ---------------------------------------------------------------------------
class OptimizationRunDB(Base):
    """ORM model for the optimization_runs table.

    One row per optimizer invocation. Provides an audit trail: when was
    the optimizer run, how many orders, which CSV was uploaded, etc.
    Linked to orders and routes via foreign keys.
    """

    __tablename__ = "optimization_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False)
    orders_assigned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orders_unassigned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vehicles_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    optimization_time_ms: Mapped[float | None] = mapped_column(Float)
    safety_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.3)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="completed")
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships — cascade delete: if a run is deleted, its orders/routes go too
    orders: Mapped[list["OrderDB"]] = relationship(
        back_populates="optimization_run", cascade="all, delete-orphan"
    )
    routes: Mapped[list["RouteDB"]] = relationship(
        back_populates="optimization_run", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# ORDERS
# ---------------------------------------------------------------------------
class OrderDB(Base):
    """ORM model for the orders table.

    One row per delivery order. Linked to an optimization run.
    Coordinates stored as PostGIS geometry for spatial queries
    (e.g., "find all orders within 2 km of the depot").
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("optimization_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_ref: Mapped[str | None] = mapped_column(String(50))
    address_raw: Mapped[str | None] = mapped_column(Text)
    address_display: Mapped[str | None] = mapped_column(String(255))
    address_original: Mapped[str | None] = mapped_column(Text)
    # PostGIS point — nullable because some orders may not be geocoded yet
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cylinder_type: Mapped[str | None] = mapped_column(String(30))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    service_time_min: Mapped[float] = mapped_column(Float, default=5.0)
    # Phase 2: delivery time windows
    # TIME type (no timezone): "deliver between 09:00 and 12:00"
    delivery_window_start: Mapped[time | None] = mapped_column()
    delivery_window_end: Mapped[time | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    geocode_confidence: Mapped[float | None] = mapped_column(Float)
    geocode_method: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    optimization_run: Mapped[OptimizationRunDB] = relationship(back_populates="orders")
    route_stops: Mapped[list["RouteStopDB"]] = relationship(back_populates="order")


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------
class RouteDB(Base):
    """ORM model for the routes table.

    One row per vehicle per optimization run. Contains the optimized
    route summary (total distance, duration, weight) and links to
    individual stops via the route_stops relationship.
    """

    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("optimization_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_id: Mapped[str] = mapped_column(String(20), nullable=False)
    driver_name: Mapped[str | None] = mapped_column(String(100))
    total_distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    total_duration_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    total_weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    optimization_run: Mapped[OptimizationRunDB] = relationship(back_populates="routes")
    stops: Mapped[list["RouteStopDB"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        # Always load stops in sequence order
        order_by="RouteStopDB.sequence",
    )


# ---------------------------------------------------------------------------
# ROUTE STOPS
# ---------------------------------------------------------------------------
class RouteStopDB(Base):
    """ORM model for the route_stops table.

    Ordered delivery stops within a route. The sequence column determines
    the driver's delivery order.

    Delivery verification fields (delivered_at, delivery_location) support
    proof-of-delivery in Phase 2+: when a driver taps "Delivered", we
    record their GPS location and timestamp. This lets us:
    - Verify the driver was at the right location
    - Build a driver-verified geocode database (better than any API!)
    - Audit delivery times for service quality
    """

    __tablename__ = "route_stops"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    address_display: Mapped[str | None] = mapped_column(String(255))
    address_original: Mapped[str | None] = mapped_column(Text)
    distance_from_prev_km: Mapped[float] = mapped_column(Float, default=0.0)
    duration_from_prev_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # Delivery verification — populated when driver marks stop as delivered
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    route: Mapped[RouteDB] = relationship(back_populates="stops")
    order: Mapped[OrderDB] = relationship(back_populates="route_stops")


# ---------------------------------------------------------------------------
# TELEMETRY
# ---------------------------------------------------------------------------
class TelemetryDB(Base):
    """ORM model for the telemetry table.

    GPS pings from driver apps. High-volume: ~25,000 rows/day at
    30-second intervals for 13 drivers across 16 hours.

    The speed_alert flag is set server-side when speed > 40 km/h in
    urban zones. This is a non-negotiable safety constraint from
    Kerala MVD directives — never remove or weaken this check.
    """

    __tablename__ = "telemetry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_id: Mapped[str] = mapped_column(String(20), nullable=False)
    driver_name: Mapped[str | None] = mapped_column(String(100))
    location = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    speed_kmh: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    speed_alert: Mapped[bool] = mapped_column(Boolean, default=False)

    # Composite indexes defined at table level for telemetry queries.
    #
    # Why composite indexes instead of single-column?
    # Telemetry queries almost always filter by (vehicle_id + time range).
    # A composite index on (vehicle_id, recorded_at DESC) lets PostgreSQL
    # satisfy "show me VEH-01's pings from the last hour" with a single
    # index scan, instead of scanning all pings and filtering.
    #
    # Why GiST for the spatial index?
    # GiST (Generalized Search Tree) is PostGIS's native index type for
    # geometry columns. It supports spatial operators like ST_DWithin
    # ("find all drivers within 500m of this point") and ST_Contains.
    # B-tree indexes can't do spatial lookups.
    # See: https://postgis.net/docs/using_postgis_dbmanagement.html#gist_indexes
    __table_args__ = (
        # "Where are all drivers now?" — spatial lookup
        # Use the same index names as init.sql to avoid duplicates.
        # Previously these had an _orm suffix, which created duplicate indexes
        # alongside the init.sql originals. Reconciled in migration after
        # ccbb9fc2db2c (see Code Review #8, finding W1).
        Index("idx_telemetry_location", location, postgresql_using="gist"),
        # "Show recent pings" — time-ordered
        Index("idx_telemetry_recorded_at", recorded_at.desc()),
        # "Show this driver's trace today" — vehicle + time
        Index(
            "idx_telemetry_vehicle_time",
            "vehicle_id",
            recorded_at.desc(),
        ),
    )


# ---------------------------------------------------------------------------
# GEOCODE CACHE
# ---------------------------------------------------------------------------
class GeocodeCacheDB(Base):
    """ORM model for the geocode_cache table.

    Every successful geocoding result is cached here. Over time, this
    becomes more valuable than any geocoding API — verified Kerala
    addresses with GPS-confirmed coordinates.

    Sources:
    - 'google': from Google Maps Geocoding API
    - 'driver_verified': GPS captured when driver delivered to this address
    - 'manual': manually corrected coordinates
    """

    __tablename__ = "geocode_cache"
    __table_args__ = (
        UniqueConstraint("address_norm", "source", name="geocode_cache_address_norm_source_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    address_raw: Mapped[str] = mapped_column(Text, nullable=False)
    address_norm: Mapped[str] = mapped_column(Text, nullable=False)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    hit_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
