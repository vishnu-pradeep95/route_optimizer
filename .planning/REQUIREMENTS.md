# Requirements: Kerala LPG Delivery Route Optimizer

**Defined:** 2026-03-10
**Core Value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route -- no silent drops, no missing stops.

## v2.1 Requirements

Requirements for v2.1 Licensing & Distribution Security. Each maps to roadmap phases.

### Enforcement Hardening

- [ ] **ENF-01**: Dev-mode code stripped from distributed builds (no ENVIRONMENT=development bypass exists in tarball)
- [ ] **ENF-02**: Licensing module compiled to native .so via Cython (replaces decompilable .pyc)
- [ ] **ENF-03**: Enforcement logic lives in compiled module with single `enforce(app)` entry point (main.py has no inline enforcement)
- [x] **ENF-04**: HMAC derivation seed rotated (old .pyc seed is compromised)

### Fingerprinting

- [x] **FPR-01**: Machine fingerprint uses /etc/machine-id + /proc/cpuinfo CPU model (replaces container_id + MAC)
- [x] **FPR-02**: Docker Compose mounts /etc/machine-id read-only into API container
- [x] **FPR-03**: get_machine_id.py updated to collect new fingerprint signals

### Runtime Protection

- [ ] **RTP-01**: SHA256 integrity manifest of protected files embedded in compiled .so
- [ ] **RTP-02**: Integrity checked at startup and during periodic re-validation
- [ ] **RTP-03**: License + integrity re-validated every 500 requests (fully offline, no internet required)

### License Management

- [ ] **LIC-01**: License renewal extends expiry without full re-keying cycle (customer drops renewal.key file)
- [ ] **LIC-02**: X-License-Expires-In response header on API responses for monitoring
- [ ] **LIC-03**: License status included in /health endpoint body for diagnostics

### Build Pipeline

- [ ] **BLD-01**: build-dist.sh pipeline: strip dev-mode → hash protected files → Cython compile → validate .so import → package tarball
- [ ] **BLD-02**: Build-time .so import validation inside Docker before packaging (catches platform mismatch)
- [ ] **BLD-03**: Cython -O2 optimization flags and embedsignature=False applied

### Testing & Documentation

- [ ] **DOC-01**: E2E tests for integrity failure, periodic re-validation, license renewal, fingerprint mismatch scenarios
- [ ] **DOC-02**: docs/LICENSING.md, SETUP.md, ERROR-MAP.md updated for all v2.1 changes
- [ ] **DOC-03**: Customer migration procedure documented (fingerprint formula change + HMAC seed rotation)

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Protection

- **ADV-01**: Fingerprint similarity scoring (fuzzy match on partial signal changes)
- **ADV-02**: Renewal notification logging (WARNING at 30 days, ERROR in grace period)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Call-home license verification | Offline deployment requirement is a hard constraint |
| Hardware dongle support | Overkill for single-customer deployment |
| Centralized license server | Makes sense at 50+ customers, not 1 |
| Code obfuscation (PyArmor, pyobfuscate) | Obfuscation theater -- Cython .so is sufficient deterrent |
| Multi-browser testing | All users on Chrome |
| Visual regression tests | Requires baseline image management, not needed for security milestone |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENF-01 | Phase 6 | Pending |
| ENF-02 | Phase 6 | Pending |
| ENF-03 | Phase 7 | Pending |
| ENF-04 | Phase 6 | Complete |
| FPR-01 | Phase 5 | Complete |
| FPR-02 | Phase 5 | Complete |
| FPR-03 | Phase 5 | Complete |
| RTP-01 | Phase 7 | Pending |
| RTP-02 | Phase 8 | Pending |
| RTP-03 | Phase 8 | Pending |
| LIC-01 | Phase 9 | Pending |
| LIC-02 | Phase 9 | Pending |
| LIC-03 | Phase 9 | Pending |
| BLD-01 | Phase 6 | Pending |
| BLD-02 | Phase 6 | Pending |
| BLD-03 | Phase 6 | Pending |
| DOC-01 | Phase 10 | Pending |
| DOC-02 | Phase 10 | Pending |
| DOC-03 | Phase 10 | Pending |

**Coverage:**
- v2.1 requirements: 19 total
- Mapped to phases: 19/19
- Unmapped: 0

---
*Requirements defined: 2026-03-10*
*Last updated: 2026-03-10 after roadmap creation*
