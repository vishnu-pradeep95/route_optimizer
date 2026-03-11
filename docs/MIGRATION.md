# Customer Migration: v2.1 Licensing Changes

> **Audience:** Developer / Support
>
> **Written:** Phase 6 (while implementation context is fresh)
> **Executed:** Phase 10 (shipped with all v2.1 changes)

---

## Overview

v2.1 introduces two breaking changes to the licensing system:

1. **Machine fingerprint formula updated** -- more stable across Docker operations
2. **License key signing credentials rotated** -- security hardening

Both changes invalidate ALL existing license keys. Customers must obtain new
license keys before upgrading to v2.1.

## Impact

- **All existing license keys will stop working** after upgrade
- No grace period or dual-key support -- clean break by design
- New keys can be generated immediately after upgrade

### Why two breaks?

| Change | Phase | What broke | Why |
|--------|-------|------------|-----|
| Fingerprint formula | Phase 5 | Machine identity hash changed | Old formula (hostname+MAC+container_id) was unstable in Docker and WSL2 |
| HMAC seed rotation | Phase 6 | Key signature no longer verifies | Old seed was human-readable and trivially extractable from .pyc |

Even if one break were somehow bypassed, the other independently invalidates
old keys. This is deliberate defense-in-depth.

## Pre-Upgrade Steps (performed by developer/support)

1. **Collect new machine fingerprint** from the customer machine:

   ```bash
   python scripts/get_machine_id.py
   ```

   The customer sends the fingerprint hash (64-character hex string).

2. **Generate new license key** with updated credentials:

   ```bash
   python scripts/generate_license.py \
       --customer "customer-name" \
       --fingerprint "new-fingerprint-hash" \
       --months 12 \
       --verify
   ```

   The `--verify` flag confirms the key decodes correctly before sending.

3. **Send new license key** to the customer via the usual channel.

## Upgrade Steps (performed by customer)

1. **Save new license key** (before upgrading):
   - Set `LICENSE_KEY` environment variable in `.env`, OR
   - Save to `license.key` file in the project root

2. **Stop the running system:**

   ```bash
   docker compose down
   ```

3. **Extract new distribution tarball** (overwrites existing):

   ```bash
   tar xzf kerala-delivery-v2.1.tar.gz
   ```

4. **Start the system:**

   ```bash
   docker compose up -d
   ```

5. **Verify license is active:**

   ```bash
   # Check license status in /health body
   curl -s http://localhost:8000/health | python3 -m json.tool
   ```

   Expected output:

   ```json
   {
     "status": "healthy",
     "license": {
       "status": "valid",
       "expires_at": "2027-03-11",
       "days_remaining": 365,
       "fingerprint_match": true
     }
   }
   ```

   Verify:
   - `license.status` is `"valid"`
   - `license.fingerprint_match` is `true`

   Also check response headers:

   ```bash
   curl -sI http://localhost:8000/health | grep -i "X-License"
   ```

   Expected:
   ```
   X-License-Expires-In: 365d
   ```

6. **Verify API endpoints are accessible:**

   ```bash
   # Should return 200 (not 503)
   curl -o /dev/null -s -w "%{http_code}" http://localhost:8000/api/routes
   ```

## Rollback

If issues arise, the customer can revert to the previous version:

1. Stop: `docker compose down`
2. Re-extract old tarball: `tar xzf kerala-delivery-v1.x.tar.gz`
3. Restore old license key (the one that worked with the previous version)
4. Start: `docker compose up -d`

Old and new license keys are **NOT interchangeable** between versions. The old
key works only with the old version; the new key works only with v2.1+.

## Checklist

- [ ] Customer fingerprint collected (new formula: machine-id + CPU model)
- [ ] New license key generated and verified (`--verify` flag)
- [ ] New key sent to customer
- [ ] Customer confirms key saved to `.env` or `license.key`
- [ ] Upgrade performed (tarball extracted, system restarted)
- [ ] `curl /health` shows `license.status = "valid"` and `fingerprint_match = true`
- [ ] Response headers include `X-License-Expires-In: {N}d`
- [ ] `/api/routes` returns 200 (not 503)
- [ ] Old tarball retained as rollback option

## Timeline

| Phase | Status | Action |
|-------|--------|--------|
| Phase 5 | Complete | Fingerprint formula changed (machine-id + CPU model) |
| Phase 6 | Complete | HMAC credentials rotated, Cython .so compilation, migration docs written |
| Phase 7 | Complete | File integrity checking, enforcement module |
| Phase 8 | Complete | Periodic re-validation (every 500 requests) |
| Phase 9 | Complete | License renewal via file drop, X-License-Expires-In header, /health license section |
| Phase 10 | Complete | End-to-end validation, documentation rewrite |

---

## What's New in v2.1

### Breaking changes (require new license key)

1. **Fingerprint formula changed** -- Now uses `/etc/machine-id` + CPU model (stable across Docker recreation and WSL2 reboots). Old keys generated with the v1.x formula will not validate.
2. **HMAC signing credentials rotated** -- New seed stored as `bytes.fromhex()` with PBKDF2 200k iterations. Old keys cannot be verified against the new credentials.

### New features

3. **License renewal via file drop** -- Generate a `renewal.key` with `--renew` flag, customer drops the file and restarts. No new fingerprint exchange needed.
4. **Monitoring headers** -- `X-License-Expires-In` header on all responses shows days until expiry. `X-License-Warning` header during grace period.
5. **License status in /health** -- The `/health` endpoint body includes a `license` section with status, expiry date, days remaining, and fingerprint match.
6. **File integrity checking** -- SHA256 manifest of protected files embedded in compiled `.so`, verified at startup and every 500 requests.
7. **Periodic re-validation** -- License expiry and file integrity re-checked every 500 requests (offline, no network calls).
8. **Native .so compilation** -- Licensing module compiled via Cython to native `.so` instead of interpreted formats.

For full details, see [LICENSING.md](LICENSING.md).
