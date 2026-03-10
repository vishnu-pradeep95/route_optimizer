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
   curl http://localhost:8000/health
   ```

   Response should show `"license": "valid"`.

## Rollback

If issues arise, the customer can revert to the previous version:

1. Stop: `docker compose down`
2. Re-extract old tarball: `tar xzf kerala-delivery-v1.x.tar.gz`
3. Restore old license key (the one that worked with the previous version)
4. Start: `docker compose up -d`

Old and new license keys are **NOT interchangeable** between versions. The old
key works only with the old version; the new key works only with v2.1+.

## Checklist

- [ ] Customer fingerprint collected (new formula)
- [ ] New license key generated and verified
- [ ] New key sent to customer
- [ ] Customer confirms key saved to .env or license.key
- [ ] Upgrade performed
- [ ] `curl /health` shows license valid
- [ ] Old tarball retained as rollback option

## Timeline

| Milestone | Action |
|-----------|--------|
| Phase 5 (complete) | Fingerprint formula changed |
| Phase 6 (current) | HMAC credentials rotated, migration docs written |
| Phase 10 (future) | Migration executed for all customers |
