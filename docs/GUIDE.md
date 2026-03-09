# Beginner's Guide to the Routing Optimization Platform

> **Audience:** Developer

> **Who this is for:** You're new to programming or new to this project. This guide
> explains what the system does, how all the pieces fit together, and how to think
> about it — using plain language and analogies. No prior knowledge assumed.

---

## Table of Contents

1. [What Does This Project Do?](#1-what-does-this-project-do)
2. [The Real-World Problem](#2-the-real-world-problem)
3. [How the System Solves It (The Big Picture)](#3-how-the-system-solves-it-the-big-picture)
4. [The Architecture — Think of It Like a Restaurant Kitchen](#4-the-architecture--think-of-it-like-a-restaurant-kitchen)
5. [The Technology Stack — What Each Tool Does](#5-the-technology-stack--what-each-tool-does)
6. [How the Code Is Organized](#6-how-the-code-is-organized)
7. [Key Concepts You'll Encounter](#7-key-concepts-youll-encounter)
8. [How Data Flows Through the System](#8-how-data-flows-through-the-system)
9. [Setup & Running the System](#9-setup--running-the-system)
10. [How to Read the Code (Learning Path)](#10-how-to-read-the-code-learning-path)
11. [How the AI Agents Help You Build](#11-how-the-ai-agents-help-you-build)
12. [Project Status](#12-project-status)
13. [Glossary](#13-glossary)

---

## 1. What Does This Project Do?

Imagine you run a delivery business with a fleet of small cargo vehicles (Piaggio
three-wheelers in Kerala, India). Every day you get 30–50 delivery orders, each
going to a different address. You have 13 vehicles and drivers.

**The question:** Which driver should deliver to which addresses, and in what order?

If you plan by hand, drivers zig-zag across the city, waste fuel, and take longer.
This system uses **computer algorithms** to figure out the most efficient routes —
like Google Maps on steroids, but for an entire fleet simultaneously.

**In one sentence:** Upload a list of deliveries → the system calculates the best
route for each vehicle → drivers follow optimized routes on their phones.

---

## 2. The Real-World Problem

This is a well-studied problem in computer science called the **Vehicle Routing
Problem (VRP)**. Think of it like this:

> You're a pizza shop with 5 delivery drivers and 40 orders. Each driver's scooter
> can carry at most 8 pizzas. Which orders go to which driver? What order should
> each driver visit their stops?

The "Capacitated" version (CVRP) adds the constraint that each vehicle has a
weight limit. Our three-wheelers can carry about 446 kg, so we can't just pile
all deliveries onto one vehicle.

**Why not just use Google Maps?** Google Maps optimizes a route for ONE driver.
We need to split 50 deliveries across 13 vehicles, respecting weight limits,
time windows, and driver shifts — while minimizing total distance for the
entire fleet. That's a much harder problem.

---

## 3. How the System Solves It (The Big Picture)

Here's the full flow in plain English:

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  1. UPLOAD        │     │  2. GEOCODE       │     │  3. OPTIMIZE      │
│                   │     │                   │     │                   │
│  Someone uploads  │────▶│  Turn addresses   │────▶│  A math solver    │
│  a spreadsheet    │     │  into GPS coords  │     │  figures out the  │
│  of today's       │     │  (latitude,       │     │  best routes for  │
│  deliveries       │     │   longitude)      │     │  all vehicles     │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                                          │
                                                          ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  6. TRACK         │     │  5. DELIVER       │     │  4. SAVE & SERVE  │
│                   │     │                   │     │                   │
│  GPS pings show   │◀────│  Drivers follow   │◀────│  Routes saved to  │
│  where drivers    │     │  their route on   │     │  database, served │
│  are in real-time │     │  a mobile-friendly│     │  to driver phones │
│  on a dashboard   │     │  web app          │     │  and dashboard    │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

Each of these steps is handled by a different part of the system. That's
the "modular" part — each piece does one job and can be swapped out independently.

---

## 4. The Architecture — Think of It Like a Restaurant Kitchen

A good restaurant kitchen has **stations** — one for grilling, one for salads,
one for desserts. Each station has specialized tools and a clear job. The head
chef coordinates, but each station works independently.

Our system works the same way:

| Kitchen Station | System Module | What It Does |
|-----------------|---------------|--------------|
| **Ingredients receiving** | `core/data_import/` | Takes in raw orders (CSV spreadsheet) |
| **Ingredient prep** | `core/geocoding/` | Converts messy addresses → precise GPS locations |
| **The stove** | `core/routing/` | Calculates how long it takes to drive between any two points |
| **The head chef's brain** | `core/optimizer/` | Figures out the best route for each vehicle |
| **The plates** | `core/models/` | Standard formats for orders, routes, vehicles (data shapes) |
| **The fridge** | `core/database/` | Saves everything permanently (PostgreSQL database) |
| **The dining room** | `apps/kerala_delivery/api/` | Serves data to the outside world (API) |
| **The menu board** | `apps/kerala_delivery/dashboard/` | Visual display of what's happening (React dashboard) |
| **The take-away window** | `apps/kerala_delivery/driver_app/` | What drivers see on their phones (PWA) |

### The Key Design Rule: Core vs. Apps

```
core/   = Generic kitchen equipment (works for any restaurant)
apps/   = Recipes specific to a particular restaurant

core/ NEVER knows about apps/.
apps/ imports and uses core/.
```

This means if someone in Mumbai wants to run a food delivery business, they'd
create `apps/mumbai_food/` with their own recipes — but use the exact same
kitchen equipment from `core/`.

---

## 5. The Technology Stack — What Each Tool Does

Don't worry about understanding all of these right now. This is a reference for
when you encounter them in the code.

### The Database — PostgreSQL + PostGIS

**What:** A database stores all our data permanently (orders, routes, GPS pings).
PostgreSQL is the database engine. PostGIS is an add-on that makes it understand
geography (GPS coordinates, distances, "find all points within 5 km").

**Analogy:** PostgreSQL is a filing cabinet. PostGIS adds a built-in map to the
filing cabinet so you can ask "find all delivery addresses near this location."

### The Routing Engine — OSRM

**What:** OSRM (Open Source Routing Machine) is like the brain of Google Maps.
Given two GPS coordinates, it tells you: "It takes 12 minutes and 3.4 km to drive
between these points, following real roads."

**How it works:** We feed it a map of Kerala downloaded from OpenStreetMap (a free,
community-maintained map database). OSRM pre-processes this map data so it can
answer routing questions in milliseconds.

**Analogy:** OSRM is like a taxi driver who has memorized every street in Kochi.
You give two addresses, and they instantly say "8 minutes, take MG Road."

### The Optimizer — VROOM

**What:** VROOM solves the Vehicle Routing Problem. You give it:
- A list of deliveries (with locations and weights)
- A list of vehicles (with capacity limits)
- A "distance/time matrix" from OSRM (how long between every pair of addresses)

And it returns: "Driver 1 goes A→B→D→F. Driver 2 goes C→E→G→H" — optimized
to minimize total driving time/distance, while respecting vehicle weight limits.

**Analogy:** If OSRM is the taxi driver who knows every road, VROOM is the
dispatcher who decides which taxi gets which passengers to cover everyone
efficiently.

### The Backend — FastAPI (Python)

**What:** FastAPI is a Python web framework. It creates the **API** — the bridge
between the database/optimizer and the user-facing apps (dashboard, driver app).

**Analogy:** FastAPI is the restaurant's order window. The kitchen works behind it,
and customers (apps) make requests through it: "Upload these orders," "Give me
Driver 3's route," "Mark delivery as complete."

### The Driver App — PWA

**What:** A Progressive Web App. It's a website that behaves like a phone app —
drivers open it in Chrome, and it shows their route, stop list, and buttons to
mark deliveries as done.

**Why not a real app?** Building native Android/iOS apps requires specialized
skills. A PWA works on any phone with Chrome and was much faster to build.

### The Dashboard — React + MapLibre GL JS

**What:** A web dashboard for the operations manager showing: all vehicles on a map
in real-time, delivery progress, historical route data.

**MapLibre GL JS** renders the actual map (using free OpenStreetMap tile data).
**React** is the UI framework that makes the page interactive.

### Docker — Container Orchestration

**What:** Docker packages each service (database, OSRM, VROOM, API) into isolated
"containers" that run the same way on any computer. Docker Compose starts
all containers together with one command.

**Analogy:** Docker is like a shipping container for software. Instead of saying
"install PostgreSQL 16, then compile PostGIS 3.5, then configure it with these
specific settings..." you just say `docker compose up` and everything appears,
correctly configured.

### Alembic — Database Migrations

**What:** When the database schema (table structure) needs to change, Alembic
creates versioned migration scripts that can upgrade or downgrade the database.

**Analogy:** Think of it like version-controlled blueprints for a building. If you
add a new room (table column), the migration says exactly what to add and how to
undo it. Every developer applies the same migrations to keep databases in sync.

---

## 6. How the Code Is Organized

Here's the folder structure with plain-English explanations:

```
routing_opt/
│
├── core/                      ← The engine room (generic, reusable)
│   ├── models/                ← Data shapes (what does an Order look like?)
│   ├── routing/               ← Talk to OSRM ("how far between A and B?")
│   ├── optimizer/             ← Talk to VROOM ("plan the best routes")
│   ├── geocoding/             ← Talk to Google Maps ("where is this address?")
│   ├── database/              ← Talk to PostgreSQL ("save this, load that")
│   ├── data_import/           ← Read CSV files ("parse this spreadsheet")
│   └── licensing/             ← Hardware-bound license key validation
│
├── apps/kerala_delivery/      ← Kerala-specific business logic
│   ├── config.py              ← All Kerala numbers (speed limits, weights, etc.)
│   ├── api/main.py            ← The API server (FastAPI endpoints)
│   ├── driver_app/            ← What drivers see on their phones
│   └── dashboard/             ← What the ops manager sees on their computer
│
├── tests/                     ← Automated tests (420 of them!)
│   ├── core/                  ← Tests for each core module
│   ├── apps/                  ← Tests for API endpoints
│   └── integration/           ← End-to-end tests (whole pipeline)
│
├── infra/                     ← Infrastructure setup
│   ├── postgres/init.sql      ← Database table definitions
│   └── alembic/               ← Database migration scripts
│
├── data/                      ← Sample data and cached results
├── docs/                      ← All documentation files
├── scripts/                   ← Utility scripts (setup, comparison, import)
├── docker-compose.yml         ← One command to start all services
└── .github/agents/            ← AI agent definitions for Copilot
```

### The Interface Pattern (Why It Matters)

Each core module defines an **interface** — a contract that says "any routing
engine must be able to answer these questions." Then we write a specific
implementation that fulfills that contract.

```
Interface (the contract):     "Any routing engine must have get_travel_time()"
     │
     ├── OSRM Adapter:        "I use OSRM to answer get_travel_time()"
     ├── (Future) Valhalla:    "I use Valhalla to answer get_travel_time()"
     └── (Future) Google Maps: "I use Google API to answer get_travel_time()"
```

**Why?** If next year we want to switch from OSRM to Valhalla (a different routing
engine), we only change one file — the adapter. Everything else in the system
keeps working because it talks to the *interface*, not the specific implementation.

**Real-world analogy:** A power outlet is an interface. Any device with the right
plug works — lamp, phone charger, blender. You can swap devices without rewiring
the house.

---

## 7. Key Concepts You'll Encounter

### Protocols (Python)

In the code, you'll see things like:

```python
class RoutingEngine(Protocol):
    def get_travel_time(self, origin, destination) -> TravelTime: ...
```

A **Protocol** defines a shape — "any object that has these methods qualifies."
Think of it as a checklist: ✅ has `get_travel_time`? Then it's a valid
`RoutingEngine`, no matter what class it is.

### Async / Await

You'll see `async def` and `await` throughout the code. This is how Python handles
multiple things at once without freezing up.

**Analogy:** When you cook dinner, you don't stand staring at the oven until the
chicken is done. You start the rice while the chicken cooks. `async`/`await`
lets the program do the same — start a database query, and while waiting for
the answer, handle another web request.

### Pydantic Models

Pydantic is a data validation library. When data enters the system (from a CSV,
from the API), Pydantic checks it:

```python
class Order(BaseModel):
    weight_kg: float = Field(gt=0)  # Must be positive
    latitude: float = Field(ge=-90, le=90)  # Valid GPS range
```

This catches bad data early — if someone uploads a CSV with negative weights
or impossible coordinates, the system rejects it with a clear error.

### SQLAlchemy ORM

The ORM (Object-Relational Mapper) lets us talk to the database using Python
objects instead of raw SQL:

```python
# Instead of: "INSERT INTO orders (order_id, weight_kg) VALUES ('ORD-001', 14.2)"
# We write:
order = OrderDB(order_id="ORD-001", weight_kg=14.2)
session.add(order)
```

This is safer (prevents SQL injection attacks) and more readable.

### Docker Compose

One file (`docker-compose.yml`) defines all services and how they connect:

```yaml
services:
  db:          # PostgreSQL + PostGIS on port 5432
  osrm:        # Routing engine on port 5000
  vroom:       # Route optimizer on port 3000
  api:         # Our FastAPI backend on port 8000
```

`docker compose up -d` starts everything. `docker compose down` stops it.

---

## 8. How Data Flows Through the System

Let's trace a single delivery order through the entire system:

### Step 1: Upload CSV
The operations person uploads a spreadsheet containing:
```
order_id,address,customer_id,cylinder_type,quantity
ORD-001,Edappally Junction Kochi,CUST-A,domestic,2
```

The **CSV Importer** (`core/data_import/csv_importer.py`) reads this file,
validates each row, and creates `Order` objects.

### Step 2: Geocode
The address "Edappally Junction Kochi" needs to become GPS coordinates.
The **Geocoder** (`core/geocoding/google_adapter.py`) calls Google Maps API:
- First checks the cache: "Have we geocoded this address before?"
- If yes: use cached coordinates instantly (free!)
- If no: call Google API → `(9.9816, 76.2999)` → cache for next time

### Step 3: Build Distance Matrix
OSRM calculates how long it takes to drive between every pair of delivery
locations. For 30 deliveries, that's a 30×30 grid of travel times.

### Step 4: Optimize
VROOM receives the delivery locations, weights, vehicle fleet, and distance
matrix. In **milliseconds**, it solves the Vehicle Routing Problem:
- Driver 1: Depot → ORD-001 → ORD-007 → ORD-015 → Depot (total: 8.2 km)
- Driver 2: Depot → ORD-003 → ORD-012 → ORD-022 → Depot (total: 7.4 km)
- etc.

### Step 5: Save to Database
The optimized routes are saved to PostgreSQL. Each route, each stop,
and the full optimization run are recorded for history.

### Step 6: Serve to Drivers
Driver opens the PWA on their phone. The API serves their personal route:
a list of stops in order, with addresses and a map showing the path.

### Step 7: Track Progress
As the driver delivers, they tap "Delivered" at each stop. Their phone
sends GPS pings every 15 seconds. The dashboard shows their position
on a live map.

---

## 9. Setup & Running the System

For complete setup instructions (Python, Docker, OSRM data, Node.js, environment variables), see [SETUP.md](SETUP.md).

---

## 10. How to Read the Code (Learning Path)

If you're new, don't try to understand everything at once. Follow this order:

### Level 1: Data Models (easiest)
**Start here.** Read the files in `core/models/`. These define the shapes of data —
what an Order looks like, what a Vehicle looks like, what a Route contains.

1. [core/models/location.py](core/models/location.py) — GPS coordinates with validation
2. [core/models/order.py](core/models/order.py) — A delivery order (weight, address, priority)
3. [core/models/vehicle.py](core/models/vehicle.py) — Vehicle specs (capacity, speed)
4. [core/models/route.py](core/models/route.py) — A route with stops, times, distances

These are pure data definitions with Pydantic validation. No external services needed.

### Level 2: Interfaces
Read the interfaces (contracts) to understand what each module promises:

5. [core/routing/interfaces.py](core/routing/interfaces.py) — "A routing engine can calculate travel times"
6. [core/optimizer/interfaces.py](core/optimizer/interfaces.py) — "An optimizer can plan routes"
7. [core/geocoding/interfaces.py](core/geocoding/interfaces.py) — "A geocoder can turn addresses into coordinates"
8. [core/data_import/interfaces.py](core/data_import/interfaces.py) — "A data importer can read orders from a file"

### Level 3: Implementations
Now see how the interfaces are fulfilled by real services:

9. [core/geocoding/google_adapter.py](core/geocoding/google_adapter.py) — Calls Google Maps API with caching
10. [core/routing/osrm_adapter.py](core/routing/osrm_adapter.py) — Calls OSRM for travel times
11. [core/optimizer/vroom_adapter.py](core/optimizer/vroom_adapter.py) — Calls VROOM for route optimization
12. [core/data_import/csv_importer.py](core/data_import/csv_importer.py) — Reads CSV spreadsheets

### Level 4: Database Layer
How data is persisted:

13. [core/database/connection.py](core/database/connection.py) — Database connection setup
14. [core/database/models.py](core/database/models.py) — ORM models (database table definitions)
15. [core/database/repository.py](core/database/repository.py) — CRUD operations (save/load data)

### Level 5: API & Business Logic
How it all comes together:

16. [apps/kerala_delivery/config.py](apps/kerala_delivery/config.py) — All Kerala-specific constants
17. [apps/kerala_delivery/api/main.py](apps/kerala_delivery/api/main.py) — The full API (read top to bottom)

### Level 6: Frontend
The visual layer:

18. [apps/kerala_delivery/dashboard/src/types.ts](apps/kerala_delivery/dashboard/src/types.ts) — TypeScript data types
19. [apps/kerala_delivery/dashboard/src/lib/api.ts](apps/kerala_delivery/dashboard/src/lib/api.ts) — Frontend API client
20. [apps/kerala_delivery/dashboard/src/pages/LiveMap.tsx](apps/kerala_delivery/dashboard/src/pages/LiveMap.tsx) — The main dashboard page

### Level 7: Tests
Tests are documentation. Read them to see how each module is meant to be used:

21. [tests/core/models/test_models.py](tests/core/models/test_models.py) — How models validate data
22. [tests/integration/test_osrm_vroom_pipeline.py](tests/integration/test_osrm_vroom_pipeline.py) — The full pipeline end-to-end

### Tips for Reading the Code

- **Read the comments.** This is an educational project — every significant block
  has a comment explaining *why* it was written that way, not just *what* it does.
- **Read the docstrings.** Every function has a docstring explaining its purpose.
- **Follow the imports.** If you see `from core.routing.interfaces import RoutingEngine`,
  go read that file to understand the contract.
- **Run the tests.** Each test is a working example of how to use the module.
- **Use `grep` to trace data.** E.g., `grep -r "get_travel_time" --include="*.py"` 
  shows everywhere travel times are used.

---

## 11. How the AI Agents Help You Build

This project uses GitHub Copilot AI agents to help with development. Each agent
is a specialist:

| Agent | Role | When to Use |
|-------|------|-------------|
| **Kerala Delivery Route Architect** | Lead architect — designs and coordinates | "What should I build next?" |
| **Implementer** | Writes code following project standards | "Build the authentication system" |
| **Code Reviewer** | Reviews code for safety, quality, tests | Runs automatically after every change |
| **Deep Researcher** | Fetches and summarizes external docs | "How does OSRM's MLD algorithm work?" |
| **Partner Explainer** | Explains technical decisions simply | "Explain this to my non-technical co-founder" |
| **Session Journal** | Saves progress between sessions | End of every working session |

### How They Work Together

```
You give a task to the Architect
  │
  ├── Architect delegates research → Deep Researcher
  ├── Architect delegates coding → Implementer
  │                                     │
  │                                     ▼
  │                           Code Reviewer runs automatically
  │                           (checks safety, quality, tests)
  │                                     │
  │                                     ▼
  ├── Architect presents results + review findings to you
  │
  └── At end of session → Session Journal saves progress
```

The **Code Reviewer runs automatically** after every implementation — you don't
need to ask for it. It checks safety constraints (no countdown timers!), code
quality, test coverage, and design-doc alignment.

---

## 12. Project Status

The platform is fully functional through 24 development phases (milestones v1.0 through v1.4). All core features are complete: CDCMS/CSV upload, geocoding with PostGIS caching, VROOM+OSRM route optimization, driver PWA, operations dashboard, GPS telemetry, fleet management, hardware-bound licensing, and production deployment with Caddy reverse proxy.

For current project status and future plans, see [ROADMAP.md](../README.md) (the Development Phases section) or `.planning/PROJECT.md`.

---

## 13. Glossary

| Term | Meaning |
|------|---------|
| **API** | Application Programming Interface — how software talks to software. The backend API accepts web requests and returns data. |
| **Async** | Asynchronous programming — allows the program to handle multiple requests simultaneously without blocking. |
| **CVRP** | Capacitated Vehicle Routing Problem — finding optimal routes for multiple vehicles with weight limits. |
| **Docker** | Software that packages applications into portable, reproducible containers. |
| **FastAPI** | A Python framework for building web APIs quickly. |
| **Geocoding** | Converting a text address ("MG Road, Kochi") into GPS coordinates (9.97, 76.28). |
| **GiST Index** | A spatial database index that makes geographic queries fast (e.g., "find all points within 5 km"). |
| **GPS Telemetry** | Location data sent from driver phones (latitude, longitude, speed, heading). |
| **MapLibre GL JS** | An open-source JavaScript library for displaying interactive maps. |
| **Migration** | A versioned script that changes database table structure (add/remove columns, etc.). |
| **MLD** | Multi-Level Dijkstra — the algorithm OSRM uses to pre-process maps for fast routing. |
| **MVD** | Kerala Motor Vehicles Department — they mandate safety rules we must follow. |
| **ORM** | Object-Relational Mapper — lets you use Python objects instead of raw SQL to interact with databases. |
| **OSRM** | Open Source Routing Machine — calculates driving directions and travel times using OpenStreetMap data. |
| **PostGIS** | A PostgreSQL extension that adds geographic/spatial capabilities. |
| **PostgreSQL** | A powerful open-source relational database. |
| **Protocol** | A Python typing concept — defines a set of methods that a class must have (like an interface in other languages). |
| **Pydantic** | A Python library for data validation — ensures data has the right types and values. |
| **PWA** | Progressive Web App — a website that can work offline and feel like a native phone app. |
| **React** | A JavaScript library for building user interfaces. |
| **SRID 4326** | The standard coordinate system for GPS (WGS84) — the one your phone uses. |
| **SQLAlchemy** | A Python library for interacting with databases using Python objects instead of raw SQL. |
| **Vite** | A fast build tool for JavaScript/TypeScript projects. |
| **VRP** | Vehicle Routing Problem — the mathematical optimization of delivery routes for a fleet. |
| **VROOM** | Vehicle Routing Open-source Optimization Machine — solves VRP instances in milliseconds. |
| **WSL2** | Windows Subsystem for Linux — lets you run Linux inside Windows. |

---

## Need Help?

- **Setup help:** Follow [SETUP.md](SETUP.md) — step-by-step first-time environment setup
- **API reference:** See [README.md](../README.md) — all endpoints, CSV format, config values
- **Ask the AI:** Use the `Kerala Delivery Route Architect` agent in Copilot Chat — it knows the entire project context
