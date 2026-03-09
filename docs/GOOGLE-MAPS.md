# Google Maps API Key Setup & Troubleshooting

> **Who this is for:** An employee at the office who needs to set up or fix Google Maps
> for address lookup (geocoding). No programming knowledge required.

---

## What Google Maps Does in This System

The system uses Google Maps to convert delivery addresses into GPS coordinates (this is called "geocoding"). This only happens during CSV upload -- when you upload the daily CDCMS delivery list, the system sends each address to Google Maps and gets back a latitude and longitude. Once an address has been looked up, the result is saved locally, so the same address is never looked up twice.

If Google Maps is not working, uploads will fail, but everything else -- routes, the driver app, delivery tracking -- continues to work normally.

---

## Important: Not a License Error

If **all** pages and endpoints return errors (not just upload), the problem is likely a license issue, not Google Maps.

Google Maps errors only affect the **upload step**. If the driver app, dashboard, and other API endpoints are also failing, see [LICENSING.md](LICENSING.md#troubleshooting-license-503) for license troubleshooting instead.

---

## Setting Up a Google Maps API Key

Follow these steps to create a new API key in Google Cloud Console.

### Step 1: Open Google Cloud Console

Go to [https://console.cloud.google.com](https://console.cloud.google.com) and sign in with a Google account.

### Step 2: Create a project (or select existing)

If you don't already have a project:

1. Click the project dropdown at the top of the page (next to "Google Cloud")
2. Click **New Project**
3. Enter a name (e.g., "LPG Delivery System")
4. Click **Create**

You should see your project name appear at the top of the page.

### Step 3: Enable the Geocoding API

1. In the left sidebar, click **APIs & Services** > **Library**
2. Search for **"Geocoding API"**
3. Click on **Geocoding API** in the results
4. Click **Enable**

You should see a green checkmark and "API enabled" message.

### Step 4: Create an API key

1. In the left sidebar, click **APIs & Services** > **Credentials**
2. Click **Create Credentials** at the top of the page
3. Select **API key**

You should see a long string of letters and numbers (e.g., `AIzaSyB...`). This is your API key.

4. Click **Copy** to copy the key
5. Click **Close**

### Step 5: Set up billing

The Geocoding API requires a billing account. Google provides **$200/month in free credit**, which covers approximately **40,000 address lookups** -- far more than the ~50 deliveries per day this system handles.

1. In the left sidebar, click **Billing**
2. Follow the prompts to set up a billing account
3. Link the billing account to your project

You should see your project listed under the billing account with "Active" status.

### Step 6: Add the key to the system

Open **Ubuntu** from the Start menu and run:

```bash
cd ~/routing_opt
nano .env
```

Find the line that says `GOOGLE_MAPS_API_KEY=` and paste your key after the equals sign:

```
GOOGLE_MAPS_API_KEY=AIzaSyB-your-actual-key-here
```

Save the file (Ctrl+O, Enter, then Ctrl+X to exit).

### Step 7: Restart the API

```bash
docker compose restart api
```

Wait about 30 seconds for the API to restart.

### Step 8: Test it

Upload a CSV file through the dashboard. If addresses are converted to coordinates without errors, the key is working.

---

## Validating Your Key

To test your API key directly, open Ubuntu and run this command (replace `YOUR_KEY_HERE` with your actual key):

```bash
curl "https://maps.googleapis.com/maps/api/geocode/json?address=Vatakara,Kerala&key=YOUR_KEY_HERE"
```

You should see a JSON response with `"status": "OK"` and latitude/longitude values like:

```json
{
  "results": [
    {
      "geometry": {
        "location": {
          "lat": 11.5929,
          "lng": 75.5634
        }
      }
    }
  ],
  "status": "OK"
}
```

If you see an error status instead, check the Common Errors section below.

---

## Common Errors

### "REQUEST_DENIED"

**What it means:** Google rejected the API request.

**Common causes:** API key is missing or invalid, Geocoding API is not enabled, or the key has IP/domain restrictions blocking your server.

**Fix:**

1. Check that `GOOGLE_MAPS_API_KEY` is set in your `.env` file -- it should not be empty and should have no extra spaces
2. Go to Cloud Console > **APIs & Services** > **Library** > verify "Geocoding API" shows as **Enabled**
3. Go to Cloud Console > **APIs & Services** > **Credentials** > click your key > verify there are no IP restrictions blocking the server (if unsure, set restrictions to "None" temporarily)
4. Run the validation `curl` command above to test the key directly

### "OVER_QUERY_LIMIT"

**What it means:** Too many requests were sent too quickly, or the monthly quota has been exceeded.

**Common causes:** Uploading very large CSV files (100+ addresses at once), or billing is not set up.

**Fix:**

1. Check that billing is active in Cloud Console -- the free $200/month credit requires a billing account to be linked
2. For large uploads, wait a few minutes and retry -- the system caches results, so previously geocoded addresses will not count again
3. Check your usage: Cloud Console > **APIs & Services** > **Geocoding API** > **Metrics** -- you should see a usage chart showing how many requests you have made

### "INVALID_REQUEST"

**What it means:** The address sent to Google was empty or malformed.

**Common causes:** Empty address fields in the CSV file.

**Fix:**

1. Open the CSV file and check for rows with missing or empty address columns
2. Make sure every row has a complete address in the address field
3. See [CSV_FORMAT.md](CSV_FORMAT.md) for the required file format

### "ZERO_RESULTS"

**What it means:** Google could not find the address.

**Common causes:** The address is too vague, misspelled, or does not exist.

**Fix:**

1. Check the address in the CDCMS system -- is it complete enough for Google to find?
2. Try searching the address on [https://maps.google.com](https://maps.google.com) directly -- if Google Maps cannot find it there, the system cannot find it either
3. Add more detail to the address (post office name, landmark, pin code)

---

## Still Not Working?

If you have followed all the steps above and uploads still fail, contact the software developer with:

1. The **exact error message** shown on the upload screen
2. A **screenshot of your Cloud Console API dashboard** showing the Geocoding API status (enabled/disabled) and recent usage
3. The **result of the validation curl command** from the "Validating Your Key" section above
