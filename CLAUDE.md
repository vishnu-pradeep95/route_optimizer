# Kerala LPG Delivery Route Optimizer

## Testing Requirements

**After every feature change or bug fix to the Driver PWA (`apps/kerala_delivery/driver_app/`):**

Run comprehensive end-to-end Playwright MCP testing. Do NOT rely on human verification for functional checks. Human verification is only for subjective visual/UX feedback.

### E2E Test Checklist — Driver PWA

Start API server, navigate to `http://localhost:8000/driver/`, and systematically verify:

**1. Upload Screen (initial state)**
- [ ] Page loads without console errors
- [ ] Upload icon (🛺) renders in container
- [ ] "Today's Deliveries" heading visible
- [ ] "Upload Delivery List" button visible and clickable
- [ ] File input triggers on button click
- [ ] Upload status area present

**2. Tabs & Navigation**
- [ ] "Delivery List" tab visible with list icon
- [ ] "Map View" tab visible with map icon
- [ ] Tab switching works (list ↔ map)

**3. Route View (after CSV upload + vehicle selection)**
- [ ] Header shows route info and stats
- [ ] Progress bar renders with correct segments
- [ ] "Last updated" timestamp + Refresh button visible
- [ ] Hero card shows for first pending stop
- [ ] Compact cards show for remaining stops
- [ ] Navigate button (full-width, 66px)
- [ ] Done + Fail buttons (60px each)

**4. Interactions**
- [ ] "Done" marks stop delivered, toast appears, auto-advance works
- [ ] "Fail" opens dark dialog modal (NOT browser confirm)
- [ ] Fail modal: reason dropdown, "Yes, Failed" + "Cancel" buttons
- [ ] Cancel closes modal without action
- [ ] "Yes, Failed" marks stop, red toast, auto-advance
- [ ] Call Office FAB visible (bottom-right, phone icon)
- [ ] All-done banner appears when all stops complete

**5. Responsiveness**
- [ ] Mobile viewport (393x851) — no overflow, no clipping
- [ ] Elements scale correctly on small screens

**6. Navigation Flow**
- [ ] Upload → Vehicle Selector → Route View → full cycle
- [ ] ⇄ (reset) button returns to vehicle selector
- [ ] "Upload New List" returns to upload screen
- [ ] Navigate button opens Google Maps in new tab

**7. All-Done State**
- [ ] Select a 1-stop vehicle (VEH-02), mark Done
- [ ] Green "Route complete!" banner appears
- [ ] Progress bar fully green
- [ ] Banner dismiss (x) button works

**8. API Endpoints**
- [ ] `GET /health` — 200
- [ ] `GET /driver/` — serves PWA index.html
- [ ] `POST /api/upload-orders` — accepts CSV/Excel files
- [ ] `GET /api/routes` — returns all routes
- [ ] `GET /api/routes/{vehicle_id}` — returns route data
- [ ] `POST /api/routes/{vehicle_id}/stops/{order_id}/status` — updates delivery status
- [ ] `GET /api/vehicles` — returns vehicle list
- [ ] `GET /api/runs` — returns optimization runs
- [ ] `POST /api/telemetry` — accepts telemetry data

### How to Test

**Docker rebuild required for API changes:** The API runs in Docker. After modifying `api/main.py` or any Python code:
```bash
docker compose build api && docker compose up -d --no-deps api
```

Use Playwright MCP tools:
1. `browser_navigate` to the driver app URL
2. `browser_snapshot` to get accessibility tree
3. `browser_click` / `browser_type` to interact
4. `browser_console_messages` to check for errors
5. `browser_take_screenshot` for visual verification

Traverse every button, link, and interactive element. Check console for errors after each action.

## Coding Conventions

- Tailwind v4 prefix: `tw:` (colon, not hyphen)
- DaisyUI components: `tw:btn`, `tw:badge`, `tw:table`
- CSS selectors: `.tw\:flex`, `.tw\:card-body`
- Driver PWA: single `index.html` file, no build step, vanilla JS
- Dashboard: React/TypeScript/Vite with Tailwind v4 + DaisyUI
