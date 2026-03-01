# LPG Delivery Route Optimizer — Office Setup & Daily Use Guide

> **Who this is for:** An employee at the office who needs to set up this system on
> a laptop and use it daily to optimize delivery routes. No programming knowledge
> required — just follow the steps.
>
> **What this does:** Takes the daily CDCMS delivery list, figures out the best
> route for each driver (shortest distance, least fuel), and gives the driver a
> Google Maps link they can follow on their phone.

---

## Table of Contents

1. [What You Need](#1-what-you-need)
2. [One-Time Setup (New Laptop)](#2-one-time-setup-new-laptop)
3. [Daily Use — Step by Step](#3-daily-use--step-by-step)
4. [Understanding the CDCMS Export](#4-understanding-the-cdcms-export)
5. [What the System Does to Addresses](#5-what-the-system-does-to-addresses)
6. [Troubleshooting](#6-troubleshooting)
7. [Costs](#7-costs)
8. [Important Rules](#8-important-rules)
9. [Quick Reference Card](#9-quick-reference-card)

---

## 1. What You Need

| Item | Details |
|------|---------|
| **Laptop** | Windows 10/11 with at least 8 GB RAM |
| **Internet** | Required for first-time setup; optional for daily use after addresses are cached |
| **CDCMS access** | Ability to export delivery lists from HPCL's CDCMS system |
| **Chrome browser** | For accessing the route optimizer web page |

---

## 2. One-Time Setup (New Laptop)

> This takes about 30–40 minutes. You only need to do this once per laptop.
> Ask the technical team if you need help with any step.

### Step 2.1: Install WSL (Windows Subsystem for Linux)

1. Open **PowerShell as Administrator** (right-click Start → "Windows PowerShell (Admin)")
2. Type this command and press Enter:
   ```
   wsl --install
   ```
3. **Restart your computer** when prompted
4. After restart, a window will open asking you to create a username and password
   - Pick a password you'll remember (at least 8 characters with letters and numbers)
   - **Remember this password** — you'll need it for setup commands

### Step 2.2: Install the Software

Open the **Ubuntu** app from your Start menu. You'll see a black terminal window.
Copy and paste each block below, one at a time, pressing Enter after each:

```bash
# Update system packages
sudo apt-get update && sudo apt-get install -y git curl python3 python3-pip python3-venv python3-dev build-essential ca-certificates gnupg
```

It will ask for your password (the one you set in Step 2.1). Type it and press Enter.
(The password won't show as you type — that's normal.)

```bash
# Install Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

**Close the Ubuntu window entirely** and reopen it from the Start menu. Then continue:

```bash
# Start Docker
sudo service docker start

# Verify Docker works
docker run --rm hello-world
```

You should see "Hello from Docker!" — that means it's working.

### Step 2.3: Download the Route Optimizer

```bash
# Clone the project (replace URL with the actual repository URL)
git clone <REPO_URL> routing_opt
cd routing_opt

# Set up Python
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2.4: Configure Settings

```bash
# Create configuration file
cp .env.example .env
nano .env
```

A text editor will open. Change these values:

| Setting | What to Put | Where to Get It |
|---------|-------------|-----------------|
| `GOOGLE_MAPS_API_KEY` | Your Google API key | Ask the technical team |
| `POSTGRES_PASSWORD` | A password (mix letters + numbers, 12+ chars, e.g., `kX9m2pL7qR4z`) | Choose your own — write it down somewhere safe |
| `API_KEY` | A password for the API (mix letters + numbers, 12+ chars, e.g., `rT5nW8jK2mP9`) | Choose your own — write it down somewhere safe |

Press `Ctrl+O` to save, then `Ctrl+X` to exit.

### Step 2.5: Set Up the Map Data

This downloads Kerala road map data so the system can calculate driving distances.
Takes about 10 minutes.

```bash
# Start Docker
sudo service docker start

# Download Kerala map data
mkdir -p data/osrm
wget -O data/osrm/kerala-latest.osm.pbf \
  https://download.openstreetmap.fr/extracts/asia/india/kerala.osm.pbf

# Process the map data (takes 5-10 minutes — wait for it to finish)
docker run --rm -v $(pwd)/data/osrm:/data osrm/osrm-backend:latest \
  osrm-extract -p /opt/car.lua /data/kerala-latest.osm.pbf

docker run --rm -v $(pwd)/data/osrm:/data osrm/osrm-backend:latest \
  osrm-partition /data/kerala-latest.osrm

docker run --rm -v $(pwd)/data/osrm:/data osrm/osrm-backend:latest \
  osrm-customize /data/kerala-latest.osrm
```

### Step 2.6: Start Everything

```bash
# Start all services
docker compose up -d

# Set up the database
source .venv/bin/activate
alembic upgrade head
```

### Step 2.7: Verify It Works

```bash
# Check if the system is running
curl http://localhost:8000/health
```

You should see `{"status": "ok", ...}`. If yes — setup is complete!

Open Chrome and go to: **http://localhost:8000/driver/** — you should see the driver app.

---

## 3. Daily Use — Step by Step

### Every Morning (or Start of Shift)

#### Step 3.1: Start the System

Open **Ubuntu** from the Start menu and run:

```bash
cd routing_opt
sudo service docker start
docker compose up -d
source .venv/bin/activate
```

Wait about 30 seconds for everything to start.

#### Step 3.2: Export from CDCMS

1. Log in to the CDCMS system
2. Go to the delivery allocation page
3. Export the day's deliveries (the "Print" or "Export" option)
4. Save the file to your Downloads folder
5. Copy it to the project:
   ```bash
   cp /mnt/c/Users/YOUR_USERNAME/Downloads/cdcms_export.csv data/cdcms_export.csv
   ```
   > Replace `YOUR_USERNAME` with your Windows username.
   > The file from CDCMS is tab-separated — that's fine, the system handles it.

#### Step 3.3: Upload and Optimize Routes

1. Open Chrome and go to: **http://localhost:8000/dashboard/**
2. You'll see the **Upload & Routes** page (it's the first tab)
3. **Drag and drop** the CDCMS file onto the upload area — or click "Browse" to select it
4. Click **Upload & Optimize**
5. Wait for the progress bar to finish (usually 5–15 seconds)

The system will automatically:
- Detect that it's a CDCMS file (tab-separated format)
- Clean up the messy addresses (phone numbers, abbreviations, etc.)
- Look up GPS coordinates (cached after first use — free and instant)
- Calculate the best route for each vehicle
- Save everything to the database

#### Step 3.4: Print QR Codes for Drivers

After optimization completes, you'll see route cards for each vehicle. You have two options:

**Option A: Print All QR Codes at Once (Recommended)**

1. Click the **🖨️ Print QR Sheet** button at the top of the results
2. A new page opens with one QR card per vehicle, formatted for A4 paper
3. Click **Print** (or Ctrl+P) → select your office printer
4. Cut out each card and hand it to the corresponding driver

**Option B: Show Individual QR Codes**

1. Click **Show QR** on any vehicle's route card
2. The QR code appears — the driver can scan it directly from the screen
3. Driver points their phone camera at the QR code → Google Maps opens with their route

#### Step 3.5: Drivers Use the Routes

Each driver:
1. **Scans the QR code** with their phone camera (no app needed)
2. **Google Maps opens** with their delivery route pre-loaded
3. **Follows the navigation** — Google Maps handles turn-by-turn directions
4. For routes with many stops (>11), the QR sheet will show multiple QR codes per driver labeled "Part 1", "Part 2", etc. — scan them in order

> **Tip:** Drivers can also open their route by going to **http://your-server:8000/driver/** on their phone browser and entering their vehicle ID.

### End of Day

```bash
# Stop all services (optional — saves laptop battery)
docker compose down
```

---

## 4. Understanding the CDCMS Export

The CDCMS system exports a tab-separated file with 19 columns. Here's what
the system uses vs. ignores:

### Columns We Use

| CDCMS Column | What We Do With It |
|--------------|--------------------|
| **OrderNo** | Becomes the order ID (unique identifier) |
| **OrderStatus** | Only processes "Allocated-Printed" orders (ignores cancelled, pending, etc.) |
| **ConsumerAddress** | Cleaned up and sent to Google Maps for GPS coordinates |
| **OrderQuantity** | Number of cylinders for weight calculation |
| **AreaName** | Used to filter deliveries by area (optional) |
| **DeliveryMan** | Used to filter deliveries by driver |

### Columns We Ignore (Privacy)

| CDCMS Column | Why We Ignore It |
|--------------|------------------|
| **MobileNo** | Customer phone numbers stay in CDCMS only — not stored in our system |
| **CashMemoNo** | Financial data — not needed for routing |
| **IVRSBookingNumber** | Booking reference — not needed for routing |
| **BookingDoneThroughRegistereMobile** | Booking method — not needed |
| Others (OrderDate, OrderSource, etc.) | Not relevant to route planning |

### Sample CDCMS Row

```
OrderNo: 517827
OrderStatus: Allocated-Printed
ConsumerAddress: 4/146 AMINAS VALIYA PARAMBATH NR. VALLIKKADU SARAMBI PALLIVATAKARA
OrderQuantity: 1
AreaName: VALLIKKADU
DeliveryMan: GIREESHAN ( C )
```

After preprocessing, this becomes:

```
order_id: 517827
address: 4/146 Aminas Valiya Parambath, Near Vallikkadu, Sarambi, Pallivatakara, Vatakara, Kozhikode, Kerala
quantity: 1
area_name: Vallikkadu
delivery_man: GIREESHAN ( C )
```

---

## 5. What the System Does to Addresses

CDCMS addresses are messy. The system cleans them before looking up GPS coordinates:

| Problem | Before | After |
|---------|--------|-------|
| Phone numbers in address | `HOUSE 9847862734KURUPAL` | `House Kurupal` |
| Phone annotations | `/ PH: 2511259` | (removed) |
| Missing spaces | `4/146AMINAS` | `4/146 Aminas` |
| NR. abbreviation | `NR. VALLIKKADU` | `Near Vallikkadu` |
| PO. joined to name | `KUNIYILPO.` | `Kuniyil P.O.` |
| ALL CAPS | `PALLIVATAKARA` | `Pallivatakara` |
| No city/state | `Sarambi` | `Sarambi, Vatakara, Kozhikode, Kerala` |
| Backtick markers | `` ``THANAL`` `` | `Thanal` |

**Why?** Google Maps understands "Near Vallikkadu, Vatakara, Kerala" much better than
"NR. VALLIKKADU". The cleaner the address, the more accurate the GPS coordinate.

### Address Caching

- The **first time** the system sees an address, it asks Google Maps for the GPS coordinate
- The result is **permanently saved** in the local database
- **Repeat customers** (same address) are looked up instantly from the cache — no Google API call needed
- Over time, most addresses will be cached, making daily operations free and instant

---

## 6. Troubleshooting

### "Cannot connect to Docker"

```
Cannot connect to the Docker daemon
```

**Fix:** Run `sudo service docker start` and wait 10 seconds.

### "File not found"

```
FileNotFoundError: CDCMS export file not found
```

**Fix:** Check the file path. Make sure you copied the file:
```bash
ls data/cdcms_export.csv    # Should show the file
```

If the file is in Downloads:
```bash
cp /mnt/c/Users/YOUR_USERNAME/Downloads/cdcms_export.csv data/cdcms_export.csv
```

### "Missing required columns"

```
ValueError: CDCMS export is missing required columns: {'OrderNo'}
```

**Fix:** The file isn't a proper CDCMS export. Make sure you're exporting from the correct
CDCMS page and the file has column headers like `OrderNo`, `ConsumerAddress`, etc.

### "No orders remain after filtering"

```
WARNING: No orders remain after filtering
```

**Fix:** Check your filter values:
- Is the driver name spelled exactly as in CDCMS? (case doesn't matter)
- Are there any "Allocated-Printed" orders in the file?
- Check: `head -5 data/cdcms_export.csv` to see what's in the file

### "Google Maps API key error"

```
ERROR: GOOGLE_MAPS_API_KEY not set
```

**Fix:** Make sure the API key is set in `.env`:
```bash
nano .env
# Find GOOGLE_MAPS_API_KEY= and add your key after the =
```

### System is slow / not responding

```bash
# Restart everything
docker compose down
sudo service docker start
docker compose up -d
```

Wait 1 minute, then try again.

### How to update the system

When the technical team pushes updates:

```bash
cd routing_opt
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt    # Install any new packages
alembic upgrade head               # Apply any database changes
docker compose up -d --build       # Restart with new code
```

---

## 7. Costs

| Item | Cost | Notes |
|------|------|-------|
| **Software** | ₹0 | All open-source |
| **Google Maps lookups** | ₹0 | Free tier covers 40,000 lookups/month (we use ~50/day) |
| **After addresses cached** | ₹0 | Repeat addresses are free — looked up from local database |
| **Internet** | Your existing connection | Only needed for first-time address lookups |
| **Laptop** | Your existing laptop | Runs on any Windows 10/11 laptop with 8 GB RAM |

**Bottom line:** ₹0 monthly cost. The system runs entirely on your office laptop.

---

## 8. Important Rules

These rules are built into the system and **cannot be changed**:

| Rule | Reason |
|------|--------|
| **No countdown timers** | Kerala Motor Vehicles Department (MVD) directive |
| **Minimum 30-minute delivery windows** | No "instant delivery" pressure on drivers |
| **Speed alerts at 40 km/h** | Three-wheeler safety limit |
| **No customer names/phones stored** | Privacy — personal info stays in CDCMS only |
| **1.3× safety buffer on travel times** | Kerala roads are slower than ideal; prevents rushed driving |

---

## 9. Quick Reference Card

Print this and keep it near the computer.

```
╔═══════════════════════════════════════════════════════════════╗
║              LPG ROUTE OPTIMIZER — DAILY STEPS              ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  1. OPEN Ubuntu app from Start menu                          ║
║                                                               ║
║  2. START the system:                                        ║
║     cd routing_opt                                           ║
║     sudo service docker start                                ║
║     docker compose up -d                                     ║
║                                                               ║
║  3. OPEN dashboard in Chrome:                                ║
║     http://localhost:8000/dashboard/                          ║
║                                                               ║
║  4. UPLOAD today's CDCMS export:                             ║
║     - Drag & drop file onto the Upload page                  ║
║     - Click "Upload & Optimize"                              ║
║     - Wait for routes to appear                              ║
║                                                               ║
║  5. PRINT QR codes:                                          ║
║     - Click "Print QR Sheet"                                 ║
║     - Print → cut → hand to drivers                          ║
║                                                               ║
║  6. DRIVERS scan QR → Google Maps → deliver                  ║
║                                                               ║
║  END OF DAY: docker compose down (optional)                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## Need Help?

- **Technical issues:** Contact the development team
- **CDCMS export problems:** Check that you're on the correct CDCMS page and the export includes the "Allocated-Printed" orders
- **Wrong routes:** The system depends on address quality. If a driver consistently goes to the wrong location, the address in CDCMS may need correction
