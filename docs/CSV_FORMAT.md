# CSV Format Reference

> **Audience:** Office Employee | Developer

Upload your CDCMS export or a CSV/Excel file. The system accepts `.csv`, `.xlsx`, and `.xls` files up to 10 MB. It automatically detects whether you uploaded a CDCMS export or a standard CSV -- just upload and the system figures out the rest.

---

## Accepted File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| CSV (comma-separated) | `.csv` | Most common |
| CSV (tab-separated) | `.csv` | CDCMS exports use tabs -- this is handled automatically |
| Excel (modern) | `.xlsx` | Excel 2007 and newer |
| Excel (older) | `.xls` | Excel 97-2003 |

**Limits:**
- Maximum file size: **10 MB**
- Maximum orders per upload: **1,000 rows**

---

## CDCMS Export Format

If you export your daily delivery list from HPCL's CDCMS (Cylinder Delivery & Customer Management System), upload the file as-is. Do not open it in Excel first -- CDCMS exports are tab-separated, and Excel may change the formatting.

### CDCMS Columns

The CDCMS export has 19 columns. The system only uses a few of them:

| Column | Used By System? | What It Does |
|--------|----------------|--------------|
| OrderNo | **Required** | Becomes the order ID for route planning |
| ConsumerAddress | **Required** | The delivery address -- cleaned automatically before map lookup |
| OrderStatus | Used for filtering | Only "Allocated-Printed" orders are imported |
| OrderQuantity | Used for load calculation | Number of cylinders for this order |
| AreaName | Used for grouping | Delivery area name (e.g., Vallikkadu, Rayarangoth) |
| DeliveryMan | Used for filtering | Driver assignment from CDCMS |
| OrderDate | Ignored | |
| OrderSource | Ignored | |
| OrderType | Ignored | |
| CashMemoNo | Ignored | |
| CashMemoStatus | Ignored | |
| CashMemoDate | Ignored | |
| ConsumedSubsidyQty | Ignored | |
| RefillPaymentStatus | Ignored | |
| IVRSBookingNumber | Ignored | |
| MobileNo | Ignored | |
| BookingDoneThroughRegistereMobile | Ignored | |
| IsRefillPort | Ignored | |
| EkycStatus | Ignored | |

### Status Filter

Only orders with status **"Allocated-Printed"** are imported. Orders with any other status (like "Delivered" or "Cancelled") are automatically skipped. If your file has no "Allocated-Printed" orders, you will see an error.

### Full 19-Column Header

For reference, the exact CDCMS header line (tab-separated) is:

```
OrderNo	OrderStatus	OrderDate	OrderSource	OrderType	CashMemoNo	CashMemoStatus	CashMemoDate	OrderQuantity	ConsumedSubsidyQty	AreaName	DeliveryMan	RefillPaymentStatus	IVRSBookingNumber	MobileNo	BookingDoneThroughRegistereMobile	ConsumerAddress	IsRefillPort	EkycStatus
```

---

## Standard CSV Format

If you are not using a CDCMS export, you can upload a standard CSV file. The only required column is **address**.

### Column Reference

| Column Name | Required? | Default If Missing | Notes |
|-------------|-----------|-------------------|-------|
| address | **Yes** | -- | The delivery address. Also accepts: `delivery_address`, `addr`, `customer_address` |
| order_id | No | Auto-generated (ORD-0001, ORD-0002, ...) | Unique identifier for each order |
| customer_id | No | Auto-generated (CUST-0001, CUST-0002, ...) | Customer reference |
| weight_kg | No | 14.2 | Weight in kilograms. If blank, uses the cylinder type or defaults to 14.2 kg (domestic cylinder) |
| cylinder_type | No | (not used -- weight defaults to 14.2 kg) | Used to look up weight. See recognized values below |
| quantity | No | 1 | Number of cylinders |
| priority | No | 2 | 1 = high, 2 = normal, 3 = low |
| notes | No | (empty) | Delivery instructions (e.g., "Ring bell twice") |
| latitude | No | (none) | GPS latitude. If provided with longitude, skips map lookup |
| longitude | No | (none) | GPS longitude. Must be provided with latitude |
| delivery_window_start | No | (none) | Earliest delivery time (e.g., "09:00") |
| delivery_window_end | No | (none) | Latest delivery time (e.g., "12:00") |

**Column name matching:**
- Column names are **case-insensitive** -- `Address`, `ADDRESS`, and `address` all work.
- Spaces are converted to underscores -- `order id` becomes `order_id` automatically.

### Recognized Cylinder Types

The `cylinder_type` column accepts these values (case-insensitive):

| Value | Weight |
|-------|--------|
| domestic | 14.2 kg |
| 14.2 | 14.2 kg |
| 14.2kg | 14.2 kg |
| commercial | 19.0 kg |
| 19 | 19.0 kg |
| 19kg | 19.0 kg |
| 5kg | 5.0 kg |
| 5 | 5.0 kg |

### Coordinate Bounds

If you provide latitude and longitude columns, the system checks that coordinates fall within India:
- Latitude: 6.0 to 37.0
- Longitude: 68.0 to 97.5

Coordinates outside this range are ignored, and the address is looked up on Google Maps instead.

---

## Example Rows

### Minimal Standard CSV (address only)

The simplest valid file has just one column:

```csv
address
"Kalamassery, HMT Colony, Near Bus Stop, Kochi"
"Edappally Junction, Opposite Lulu Mall, Kochi"
"Palarivattom, Bypass Road, Near Oberon Mall"
```

### Full Standard CSV (all columns)

```csv
order_id,address,customer_id,cylinder_type,quantity,priority,notes,latitude,longitude,delivery_window_start,delivery_window_end
ORD-001,"Kalamassery, HMT Colony, Near Bus Stop, Kochi",CUST-001,domestic,2,2,Ring bell twice,10.0553,76.3221,09:00,12:00
ORD-002,"Edappally Junction, Opposite Lulu Mall, Kochi",CUST-002,domestic,1,2,,9.9816,76.2996,09:00,12:00
ORD-003,"Palarivattom, Bypass Road, Near Oberon Mall",CUST-003,domestic,1,1,Urgent - elderly customer,9.9944,76.3064,06:00,09:00
```

### CDCMS Export (first 2 rows)

This is what a raw CDCMS export looks like. Upload it as-is:

```
OrderNo	OrderStatus	OrderDate	OrderSource	OrderType	CashMemoNo	CashMemoStatus	CashMemoDate	OrderQuantity	ConsumedSubsidyQty	AreaName	DeliveryMan	RefillPaymentStatus	IVRSBookingNumber	MobileNo	BookingDoneThroughRegistereMobile	ConsumerAddress	IsRefillPort	EkycStatus
517827	Allocated-Printed	14-02-2026 9:41	IVRS	Refill	1234567	Printed	14-02-2026	1	1	VALLIKKADU	GIREESHAN ( C )		'1111111111	'1111111111	Y	4/146 AMINAS VALIYA PARAMBATH NR. VALLIKKADU SARAMBI PALLIVATAKARA	N	EKYC NOT DONE
517828	Allocated-Printed	14-02-2026 10:02	IVRS	Refill	1234568	Printed	14-02-2026	1	1	VALLIKKADU	GIREESHAN ( C )		'2222222222	'2222222222	Y	8/301 "ARUNIMA"PADINJARA KALARIKKANDI MEATHALA MADAMCHORODE EAST	N	EKYC DONE
```

---

## What Can Go Wrong

### Before Processing (File-Level Errors)

These errors appear immediately after you upload the file.

| What You See | Why It Happened | How to Fix It |
|-------------|----------------|---------------|
| "Unsupported file type (.pdf). Accepted: .csv, .xls, .xlsx" | You uploaded a file that is not a CSV or Excel file. | Save your data as `.csv` or `.xlsx` and try again. |
| "Unexpected content type (application/pdf). Upload a CSV or Excel file." | The file looks like the wrong type. | Make sure you are uploading a CSV or Excel file, not a PDF or other document. |
| "File too large (15.2 MB). Maximum: 10 MB." | The file exceeds the 10 MB limit. | Split your orders into smaller files, or remove unnecessary rows. |
| "No 'Allocated-Printed' orders found in CDCMS export. Check that the file has orders with status 'Allocated-Printed'." | The system detected a CDCMS export, but every order has a status other than "Allocated-Printed" (e.g., all are "Delivered" or "Cancelled"). | Export a fresh list from CDCMS that includes today's pending orders. |
| "No valid orders found in file" | The file was read successfully but contained no usable order rows. | Check that the file has data rows below the header. |
| "Missing address column 'address' -- make sure you're uploading the correct file format" | The system could not find an address column in your standard CSV. | Rename your address column to `address`, `delivery_address`, `addr`, or `customer_address`. |
| "Required columns missing: ConsumerAddress, OrderNo -- make sure you're uploading the raw CDCMS export" | The file looks like a CDCMS export (tab-separated), but it is missing the OrderNo or ConsumerAddress column. | Make sure you exported the full report from CDCMS. Do not delete columns before uploading. |
| "The 'ConsumerAddress' column exists but all values are empty. Check the file format." | The ConsumerAddress column is present but every row has a blank address. | Check the CDCMS export -- the addresses may not have been included. Re-export from CDCMS. |
| "Unsupported file format: .txt. Use .csv, .xlsx, or .xls" | You uploaded a file with an unrecognized extension. | Rename the file to `.csv` if it contains comma-separated or tab-separated data, or save as `.xlsx`. |

### During Processing (Row-Level Errors)

These errors apply to individual rows. The system imports the valid rows and reports which rows had problems.

| What You See | Why It Happened | How to Fix It |
|-------------|----------------|---------------|
| "Empty address -- add a delivery address" | A row has no address. | Add the delivery address to that row. |
| "Duplicate order_id 'ORD-001' -- already imported from an earlier row" | Two rows have the same order ID. | Give each order a unique ID, or remove the duplicate row. |
| "Invalid weight '20kg' in weight_kg column -- using default 14.2 kg" | The weight column has a value that is not a number. This is a **warning** -- the order is still imported with the default weight. | Enter the weight as a number only (e.g., `14.2`), not with units. |
| "Invalid number value -- check for letters or symbols in numeric fields" | A numeric column (like quantity or weight) contains text instead of a number. | Remove letters or symbols from numeric columns. Use digits only (e.g., `14.2` not `14.2kg`). |
| "Unexpected value format -- check the cell contents" | A cell has an unexpected data format that the system cannot parse. | Check the cell for unusual characters or formatting. Clear the cell and re-type the value. |
| "Invalid value in this row" | A cell contains a value the system does not recognize. | Review the row for typos or incorrect data. |
| "Missing required field 'order_id' -- check your CSV has all required columns" | A required column is missing or the cell is empty in this row. | Make sure every row has values in the required columns. |
| "Empty or invalid cell -- fill in required fields" | A required cell is empty or contains only whitespace. | Fill in the empty cell with the correct value. |
| "Could not process this row -- check the data format" | The row has a data issue the system could not diagnose specifically. | Check all cells in this row for unusual formatting, then re-upload. |

### During Map Lookup (Geocoding Errors)

After importing, the system looks up each address on Google Maps. These errors mean an address could not be found.

| What You See | Why It Happened | How to Fix It |
|-------------|----------------|---------------|
| "Address not found -- check spelling in CDCMS" | Google Maps could not find this address. The address may be misspelled or too vague. | Check the address for typos. Add more detail like the area name, post office, or nearby landmark. |
| "Geocoding service blocked -- contact IT" | The Google Maps service rejected the request. This is a system configuration issue, not a problem with your file. | Contact IT to check the Google Maps API key configuration. |
| "Google Maps quota exceeded -- contact IT" | Too many addresses were looked up in a short time, exceeding the Google Maps daily or per-second limit. | Contact IT. If urgent, wait a few minutes and try uploading again with fewer new addresses. |
| "Address could not be processed -- check for unusual characters" | The address contains characters or formatting that Google Maps cannot handle. | Simplify the address -- remove special characters, brackets, or unusual punctuation and use plain text. |
| "Google Maps is temporarily unavailable -- try again in a few minutes" | Google Maps experienced a temporary error. | Try uploading again in a few minutes. If the problem persists, contact IT. |
| "Geocoding service not configured (missing API key)" | The system does not have a Google Maps API key set up. Previously looked-up addresses still work from the cache. | Contact IT to configure the Google Maps API key. |
| "Could not find this address -- try checking the spelling" | Google Maps returned a status the system does not recognize, or the address lookup failed for an unknown reason. | Check the address for typos. Try adding more detail like the post office or landmark name. |

---

## Address Cleaning (CDCMS Only)

The system automatically cleans CDCMS addresses before looking them up on Google Maps. Standard CSV addresses are **not** cleaned -- they are used as-is.

### What the System Does

When you upload a CDCMS export, each address goes through these cleaning steps:

1. **Removes phone numbers.** CDCMS sometimes puts 10-digit phone numbers inside the address (e.g., "VALIYAPARAMBATH (H) 9847862734KURUPAL" becomes "VALIYAPARAMBATH (H) KURUPAL").

2. **Removes phone annotations.** Entries like "/ PH: 2511259" or "/ 2513264" are stripped out.

3. **Removes quotation marks and backticks.** CDCMS uses these as house name markers (e.g., \`\`THANAL\`\` or "ARUNIMA"). The markers are removed but the name is kept.

4. **Expands abbreviations.** "NR." / "NR;" / "NR:" becomes "Near". "PO." / "PO" becomes "P.O." (Post Office). "(H)" becomes "House".

5. **Fixes concatenated PO names.** CDCMS often runs the post office name directly into "PO" (e.g., "KUNIYILPO." becomes "KUNIYIL P.O.").

6. **Adds spaces between numbers and text.** "8/542SREESHYLAM" becomes "8/542 Sreeshylam".

7. **Collapses extra spaces.** Multiple spaces are reduced to one.

8. **Removes dangling punctuation.** Leading or trailing semicolons, dashes, and plus signs are removed.

9. **Converts to title case.** "KALAMASSERY HMT COLONY" becomes "Kalamassery Hmt Colony". Common abbreviations like KSEB (Kerala State Electricity Board) stay uppercase.

10. **Appends location context.** ", Vatakara, Kozhikode, Kerala" is added to the end of every address. This helps Google Maps find addresses in the correct region, since CDCMS addresses rarely mention the city or state.

### Before and After Examples

| CDCMS Address (Before) | Cleaned Address (After) |
|------------------------|------------------------|
| KALAMASSERY HMT COLONY NEAR BUS STOP | Kalamassery Hmt Colony Near Bus Stop |
| VALIYAPARAMBATH (H) 9847862734KURUPAL ONTHAMKAINATTY VATAKARA | Valiyaparambath House Kurupal Onthamkainatty Vatakara |
| 4/146 AMINAS NR. VALLIKKADU | 4/146 Aminas Near Vallikkadu |
| HOUSE NR; RATION SHOP | House Near Ration Shop |
| VALIYAPARAMBATH (H) KURUPAL | Valiyaparambath House Kurupal |
