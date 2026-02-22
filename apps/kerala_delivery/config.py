"""Kerala LPG delivery business configuration.

All Kerala-specific constants live here — NOT in core/ modules.
This is the single place to tune for this business. Another business
(e.g., Mumbai food delivery) would have their own config.py.

Values sourced from:
- HPCL LPG distributor specs
- Piaggio Ape Xtra LDX vehicle specifications
- Kerala road/traffic observations
- Design doc: plan/kerala_delivery_route_system_design.md
"""

import os

from core.models.location import Location

# =============================================================================
# DEPOT (GODOWN) LOCATION
# =============================================================================
# TODO: Replace with actual godown GPS coordinates
# This is a placeholder near Kochi — update before first real run
DEPOT_LOCATION = Location(
    latitude=9.9716,
    longitude=76.2846,
    address_text="LPG Godown (Main Depot)",
)

# =============================================================================
# DELIVERY ZONE
# =============================================================================
# HPCL policy: free delivery within this radius from the depot
FREE_DELIVERY_RADIUS_KM = 5.0

# =============================================================================
# FLEET CONFIGURATION
# =============================================================================
# Number of delivery vehicles (three-wheelers)
NUM_VEHICLES = 13

# Piaggio Ape Xtra LDX specs (diesel/CNG variant)
# Rated payload: 496 kg; we use 90% for safety margin
VEHICLE_MAX_WEIGHT_KG = 446.0  # 496 × 0.9 = 446 kg

# Max cylinders per load — limited by cargo bed volume, not just weight
# Domestic 14.2 kg cylinder dimensions: ~345mm diameter × 580mm height
# Ape Xtra LDX cargo bed: ~1500mm × 1300mm × 420mm
# Practical fit: ~28-32 domestic cylinders stacked in two layers
VEHICLE_MAX_CYLINDERS = 30  # Conservative estimate; adjust after real testing

# Driver speed limit (urban Kerala) for safety alerts
SPEED_LIMIT_KMH = 40.0

# =============================================================================
# LPG CYLINDER SPECS
# =============================================================================
# Standard HPCL cylinder weights (filled)
DOMESTIC_CYLINDER_KG = 14.2   # 14.2 kg standard domestic
COMMERCIAL_CYLINDER_KG = 19.0  # 19 kg commercial
SMALL_CYLINDER_KG = 5.0       # 5 kg FTL (Free Trade LPG)

# Default if cylinder type not specified in import
DEFAULT_CYLINDER_KG = DOMESTIC_CYLINDER_KG

# Cylinder weight lookup — passed to CsvImporter so core/ stays generic.
# Keys are the cylinder_type strings that appear in CDCMS CSV exports.
CYLINDER_WEIGHTS: dict[str, float] = {
    "domestic": DOMESTIC_CYLINDER_KG,
    "14.2": DOMESTIC_CYLINDER_KG,
    "14.2kg": DOMESTIC_CYLINDER_KG,
    "commercial": COMMERCIAL_CYLINDER_KG,
    "19": COMMERCIAL_CYLINDER_KG,
    "19kg": COMMERCIAL_CYLINDER_KG,
    "5kg": SMALL_CYLINDER_KG,
    "5": SMALL_CYLINDER_KG,
}

# =============================================================================
# ROUTING & TIMING
# =============================================================================
# Safety multiplier on OSRM travel time estimates.
# Kerala narrow roads + three-wheeler speeds + traffic = 30% buffer.
# Calibrate with real GPS data after Phase 1.
SAFETY_MULTIPLIER = 1.3

# Monsoon season adds extra delay (June–September)
MONSOON_MONTHS = {6, 7, 8, 9}
MONSOON_MULTIPLIER = 1.5  # 50% extra during monsoon (on top of safety multiplier)

# Service time at each stop: unload cylinder, get signature, replace empty
SERVICE_TIME_MINUTES = 5

# =============================================================================
# DELIVERY OPERATIONS
# =============================================================================
# Typical deliveries per driver per day (for capacity planning)
MIN_DELIVERIES_PER_DRIVER = 22
MAX_DELIVERIES_PER_DRIVER = 44

# Minimum delivery window — no "instant delivery" promises
# Kerala MVD directive: no time-pressure delivery
# TODO: Enforce in ETA display when Phase 2 adds customer-facing time windows.
# Currently no violation since the driver app doesn't display ETAs to customers.
MIN_DELIVERY_WINDOW_MINUTES = 30

# Operating hours — 24-hour operations
# Shifts should be configured per business needs
DEFAULT_SHIFT_START = "06:00"
DEFAULT_SHIFT_END = "22:00"

# =============================================================================
# EXTERNAL SERVICES
# =============================================================================
# Read from environment variables so Docker Compose networking works.
# In Docker, services reference each other by container name (e.g., http://osrm:5000).
# Locally, they default to localhost.

# OSRM_URL: reserved for future direct OSRM queries (e.g., distance matrix
# endpoint, speed profile calibration). Currently VROOM calls OSRM internally,
# but we'll need direct access in Phase 2 for pre-optimization analysis.
OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5000")
VROOM_URL = os.environ.get("VROOM_URL", "http://localhost:3000")
