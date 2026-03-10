"""Kerala LPG delivery business configuration.

All Kerala-specific constants live here — NOT in core/ modules.
This is the single place to tune for this business. Another business
(e.g., Mumbai food delivery) would have their own config.py.

Values sourced from:
- HPCL LPG distributor specs
- Piaggio Ape Xtra LDX vehicle specifications
- Kerala road/traffic observations
"""

import os

from core.models.location import Location

# =============================================================================
# DEPOT (GODOWN) LOCATION
# =============================================================================
# Actual godown GPS coordinates — Vatakara, Kozhikode district
# Sourced from Google Maps pin drop at the HPCL LPG godown
DEPOT_LOCATION = Location(
    latitude=11.624443730714066,
    longitude=75.57964507762223,
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

# Buffer multiplier for QR sheet estimated route time display.
# Shows a range: "X–Y min" where Y = X * buffer.
# Separate from SAFETY_MULTIPLIER (which adjusts routing estimates).
QR_SHEET_DURATION_BUFFER = 1.2

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
# Enforced in upload_and_optimize endpoint: windows narrower than this
# are automatically widened (end time extended) before optimization.
# See: apps/kerala_delivery/api/main.py, Step 1b
MIN_DELIVERY_WINDOW_MINUTES = 30

# Operating hours — 24-hour operations
# Shifts should be configured per business needs
DEFAULT_SHIFT_START = "06:00"
DEFAULT_SHIFT_END = "22:00"

# =============================================================================
# OFFICE CONTACT
# =============================================================================
# Office phone number in E.164 format for driver "Call Office" button.
# Replace with actual office number before production deployment.
OFFICE_PHONE_NUMBER = "+910000000000"

# =============================================================================
# EXTERNAL SERVICES
# =============================================================================
# Read from environment variables so Docker Compose networking works.
# In Docker, services reference each other by container name (e.g., http://vroom:3000).
# Locally, they default to localhost.
VROOM_URL = os.environ.get("VROOM_URL", "http://localhost:3000")

# =============================================================================
# GPS TELEMETRY
# =============================================================================
# GPS accuracy threshold: pings with accuracy worse than this are discarded.
# GPS drift in dense Kerala neighborhoods can put drivers on the wrong street.
# Start at 50m (conservative). Once you have real-world accuracy data from
# drivers' phones, tune down to 30m for tighter tracking.
GPS_ACCURACY_THRESHOLD_M = 50.0

# =============================================================================
# COORDINATE BOUNDS (India-wide sanity check)
# =============================================================================
# Used by CsvImporter to discard obviously wrong coordinates.
# (lat_min, lat_max, lon_min, lon_max) — covers all of India.
# Lives here (not in core/) because bounds are region-specific.
INDIA_COORDINATE_BOUNDS = (6.0, 37.0, 68.0, 97.5)

# =============================================================================
# CDCMS PREPROCESSOR CONFIG
# =============================================================================
# Appended to every CDCMS address for geocoding context.
# CDCMS addresses rarely mention city/state — geocoders need this context.
# Change this when deploying for a different distributor's delivery zone.
CDCMS_AREA_SUFFIX = ", Vatakara, Kozhikode, Kerala"

# =============================================================================
# GEOCODING COST & DUPLICATE DETECTION
# =============================================================================
# Confidence-weighted distance thresholds for duplicate location detection (meters).
# Tighter for high-accuracy geocodes, wider for low-accuracy.
# Tunable after real-world testing with actual Vatakara addresses.
DUPLICATE_THRESHOLDS: dict[str, float] = {
    "rooftop": 10.0,          # ROOFTOP: building-level, very tight
    "interpolated": 20.0,     # RANGE_INTERPOLATED: street-level
    "geometric_center": 50.0, # GEOMETRIC_CENTER: area center, wide
    "approximate": 100.0,     # APPROXIMATE: very rough, widest
}

# Google Maps Geocoding API cost per request.
# $5 per 1000 requests = $0.005 each.
GEOCODING_COST_PER_REQUEST: float = 0.005

# Monthly free tier credit from Google Maps Platform.
GEOCODING_FREE_TIER_USD: float = 200.0
