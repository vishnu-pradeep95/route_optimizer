# LPG Delivery Route Optimizer -- Office Setup & Daily Use Guide

> **Audience:** Office Employee

> **Who this is for:** An employee at the office who needs to set up this system on
> a laptop and use it daily to optimize delivery routes. No programming knowledge
> required -- just follow the steps.
>
> **What this does:** Takes the daily CDCMS delivery list, figures out the best
> route for each driver (shortest distance, least fuel), and gives the driver a
> Google Maps link they can follow on their phone.

> **IMPORTANT:** Always use the **Ubuntu** app from the Start menu. Do NOT use
> PowerShell, Command Prompt, or Windows Terminal. All commands in this guide
> must be run in Ubuntu.

---

## Quick Start (2 Steps)

```bash
# 1. Open Ubuntu from the Start menu, then:
cd ~/routing_opt
./scripts/start.sh

# 2. Open the dashboard in Chrome
#    http://localhost:8000/dashboard/
```

The start script handles everything: starts Docker, starts all services, waits
until everything is healthy, and shows you the dashboard URL.

**First time?** Follow Section 2 below for one-time setup.

---

## Table of Contents

1. [What You Need](#1-what-you-need)
2. [One-Time Setup (New Laptop)](#2-one-time-setup-new-laptop)
3. [Daily Use -- Step by Step](#3-daily-use--step-by-step)
4. [Understanding CDCMS and CSV Formats](#4-understanding-cdcms-and-csv-formats)
5. [Troubleshooting](#5-troubleshooting)
6. [Costs & Licensing](#6-costs)
7. [Important Rules](#7-important-rules)
8. [Quick Reference Card](#8-quick-reference-card)

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

> This takes about 30--40 minutes. You only need to do this once per laptop.
> Ask the technical team if you need help with any step.

### Step 2.1: Install WSL (Windows Subsystem for Linux)

1. Open **PowerShell as Administrator** (right-click Start -> "Windows PowerShell (Admin)")
2. Type this command and press Enter:
   ```
   wsl --install
   ```
3. **Restart your computer** when prompted
4. After restart, a window will open asking you to create a username and password
   - Pick a password you'll remember (at least 8 characters with letters and numbers)
   - **Remember this password** -- you'll need it for setup commands

### 2.2 Install Everything

Open Ubuntu, navigate to the project folder, and run the setup script:

```bash
cd ~/routing_opt
./scripts/bootstrap.sh
```

This script:
- Installs Docker (if not already installed)
- Creates your configuration file
- Downloads Kerala map data (~300 MB, first time only)
- Starts all services

**First run takes about 15 minutes.** You'll see progress messages throughout.
If it asks you to restart Ubuntu, close and reopen Ubuntu, then run the command again.

### Step 2.3: Verify It Works

Open Chrome and go to: **http://localhost:8000/dashboard/** -- you should see the
operations dashboard. Go to **http://localhost:8000/driver/** -- you should see the
driver app.

---

## 3. Daily Use -- Step by Step

### Every Morning (or Start of Shift)

#### Step 3.1: Start the System

Open **Ubuntu** from the Start menu and run:

```bash
cd ~/routing_opt
./scripts/start.sh
```

Wait for the message showing the dashboard URL. This usually takes less than a minute.

#### Step 3.2: Export from CDCMS

1. Log in to the CDCMS system
2. Go to the delivery allocation page
3. Export the day's deliveries (the "Print" or "Export" option)
4. Save the file to your Downloads folder

#### Step 3.3: Upload and Optimize Routes

1. Open Chrome and go to: **http://localhost:8000/dashboard/**
2. You'll see the **Upload & Routes** page (it's the first tab)
3. **Drag and drop** the CDCMS file onto the upload area -- or click "Browse" to select it
4. The system detects the file format and shows a **driver preview** -- a list of drivers found in the file with the number of orders for each
5. **Select which drivers** to process -- deselect any drivers you don't need routes for (their orders won't be geocoded, saving API costs)
6. Click **Process Selected**
7. Wait for the progress bar to finish (usually 5--15 seconds)

The system will automatically:
- Detect that it's a CDCMS file (tab-separated format)
- Clean up the messy addresses (phone numbers, abbreviations, etc.)
- Look up GPS coordinates for the selected drivers' orders only (cached after first use -- free and instant)
- Calculate the best route for each selected vehicle
- Save everything to the database

#### Step 3.4: Print QR Codes for Drivers

After optimization completes, you'll see route cards for each vehicle. You have two options:

**Option A: Print All QR Codes at Once (Recommended)**

1. Click the **Print QR Sheet** button at the top of the results
2. A new page opens with one QR card per vehicle, formatted for A4 paper
3. Click **Print** (or Ctrl+P) -> select your office printer
4. Cut out each card and hand it to the corresponding driver

**Option B: Show Individual QR Codes**

1. Click **Show QR** on any vehicle's route card
2. The QR code appears -- the driver can scan it directly from the screen
3. Driver points their phone camera at the QR code -> Google Maps opens with their route

#### Step 3.5: Drivers Use the Routes

Each driver:
1. **Scans the QR code** with their phone camera (no app needed)
2. **Google Maps opens** with their delivery route pre-loaded
3. **Follows the navigation** -- Google Maps handles turn-by-turn directions
4. For routes with many stops (>11), the QR sheet will show multiple QR codes per driver labeled "Part 1", "Part 2", etc. -- scan them in order

> **Tip:** Drivers can also open their route by going to **http://your-server:8000/driver/** on their phone browser and entering their vehicle ID.

### End of Day

```bash
# Stop all services (optional -- saves laptop battery)
cd ~/routing_opt
./scripts/stop.sh
```

> To also clean up disk space: `./scripts/stop.sh --gc`

---

## 4. Understanding CDCMS and CSV Formats

For complete documentation on file formats, see **[CSV_FORMAT.md](CSV_FORMAT.md)**, which covers:
- What file types are accepted (.csv, .xlsx, .xls)
- Which CDCMS columns are used and which are ignored
- Standard CSV column reference
- What the system does to clean addresses
- Common error messages and how to fix them

---

## 5. Troubleshooting

### "Cannot connect to Docker"

```
Cannot connect to the Docker daemon
```

**Fix:** Run `./scripts/start.sh` -- it starts Docker automatically and waits for all services.

```bash
cd ~/routing_opt
./scripts/start.sh
```

### "Missing required columns"

```
Required columns missing: ConsumerAddress, OrderNo -- make sure you're uploading the raw CDCMS export
```

**Fix:** The file is not a proper CDCMS export. Make sure you are exporting from the correct CDCMS page and the file has column headers like OrderNo, ConsumerAddress, etc.

### "No Allocated-Printed orders found"

```
No 'Allocated-Printed' orders found in CDCMS export. Check that the file has orders with status 'Allocated-Printed'.
```

**Fix:** Check your filter values:
- Is the driver name spelled exactly as in CDCMS? (case doesn't matter)
- Are there any "Allocated-Printed" orders in the file?

### "Geocoding service not configured"

```
Geocoding service not configured (missing API key)
```

**Fix:** Contact IT -- they need to configure the Google Maps API key in the system.

> **For a complete list of error messages, see [CSV_FORMAT.md > What Can Go Wrong](CSV_FORMAT.md#what-can-go-wrong).**

### System is slow / not responding

```bash
cd ~/routing_opt
./scripts/start.sh
```

The start script restarts everything. Wait for it to finish, then try again.

### How to update the system

When the technical team pushes updates:

```bash
cd ~/routing_opt
git pull origin main
./scripts/bootstrap.sh
```

The bootstrap script rebuilds everything with the latest code.

---

## 6. Costs

| Item | Cost | Notes |
|------|------|-------|
| **Software license** | As per agreement | Hardware-bound license key required (see Section 6.1) |
| **Google Maps lookups** | 0 | Free tier covers 40,000 lookups/month (we use ~50/day) |
| **After addresses cached** | 0 | Repeat addresses are free -- looked up from local database |
| **Internet** | Your existing connection | Only needed for first-time address lookups |
| **Laptop** | Your existing laptop | Runs on any Windows 10/11 laptop with 8 GB RAM |

### 6.1 License Activation

The software requires a valid license key to operate. Without it, the system
will start but refuse to process requests.

**First-time activation:**

1. Start the system normally (`./scripts/start.sh`)
2. Open Ubuntu and run:
   ```bash
   cd ~/routing_opt
   python scripts/get_machine_id.py
   ```
3. You'll see a "Machine Fingerprint" -- a long string of letters and numbers
4. Send this fingerprint to the software provider (WhatsApp, email, etc.)
5. You'll receive a license key (starts with `LPG-`)
6. Save it:
   ```bash
   echo "LPG-XXXX-XXXX-XXXX-XXXX" > ~/routing_opt/license.key
   ```
   (Replace `LPG-XXXX-...` with the actual key you received)
7. Restart: `./scripts/start.sh`

**License renewal:** If you see warnings about license expiry, repeat steps 2--6
with a new key from the provider. The fingerprint may change if the system was
reinstalled, so always send a fresh one.

**Important:** The license is tied to this specific laptop. If you move to a new
laptop, you need a new license key.

---

## 7. Important Rules

These rules are built into the system and **cannot be changed**:

| Rule | Reason |
|------|--------|
| **No countdown timers** | Kerala Motor Vehicles Department (MVD) directive |
| **Minimum 30-minute delivery windows** | No "instant delivery" pressure on drivers |
| **Speed alerts at 40 km/h** | Three-wheeler safety limit |
| **No customer names/phones stored** | Privacy -- personal info stays in CDCMS only |
| **1.3x safety buffer on travel times** | Kerala roads are slower than ideal; prevents rushed driving |

---

## 8. Quick Reference Card

Print this and keep it near the computer.

```
+-----------------------------------------+
|         DAILY QUICK REFERENCE           |
+-----------------------------------------+
|                                         |
|  1. OPEN Ubuntu from Start menu         |
|                                         |
|  2. START the system:                   |
|     cd ~/routing_opt                    |
|     ./scripts/start.sh                  |
|                                         |
|  3. OPEN Chrome:                        |
|     http://localhost:8000/dashboard/     |
|                                         |
|  4. UPLOAD the CDCMS file               |
|     (drag & drop onto the page)         |
|                                         |
|  5. SELECT drivers to process           |
|     then click "Process Selected"       |
|                                         |
|  6. PRINT QR codes for drivers          |
|                                         |
|  7. END OF DAY (optional):              |
|     ./scripts/stop.sh                   |
|                                         |
+-----------------------------------------+
```

---

## Need Help?

- **Technical issues:** Contact the development team
- **CDCMS export problems:** Check that you're on the correct CDCMS page and the export includes the "Allocated-Printed" orders
- **Wrong routes:** The system depends on address quality. If a driver consistently goes to the wrong location, the address in CDCMS may need correction
