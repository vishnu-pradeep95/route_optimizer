# Requirements: Kerala LPG Delivery Route Optimizer

**Defined:** 2026-03-04
**Core Value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route -- no silent drops, no missing stops.

## v1.3 Requirements

Requirements for v1.3 Office-Ready Deployment. Each maps to roadmap phases.

### Installation

- [ ] **INST-01**: Bootstrap script auto-installs Docker CE in WSL if missing
- [ ] **INST-02**: Bootstrap script configures wsl.conf for Docker auto-start on boot
- [ ] **INST-03**: Bootstrap script detects Windows filesystem (`/mnt/c/`) and aborts with clear redirect
- [ ] **INST-04**: Bootstrap script pre-checks available RAM and warns if OSRM may OOM
- [ ] **INST-05**: Bootstrap script detects WSL1 vs WSL2 and fails clearly on WSL1

### Daily Operations

- [ ] **DAILY-01**: Single `start.sh` command starts Docker, runs compose up, polls health, prints URL

### CSV Documentation

- [ ] **CSV-01**: CSV_FORMAT.md documents all accepted file formats (.csv, .xlsx, .xls)
- [ ] **CSV-02**: CSV_FORMAT.md documents CDCMS columns (required/optional, status filter)
- [ ] **CSV-03**: CSV_FORMAT.md documents standard CSV columns with defaults and constraints
- [ ] **CSV-04**: CSV_FORMAT.md documents rejection reasons and what causes rows to fail
- [ ] **CSV-05**: CSV_FORMAT.md documents address cleaning pipeline with examples
- [ ] **CSV-06**: CSV_FORMAT.md includes example rows for both CDCMS and standard CSV

### Documentation Fixes

- [ ] **DOCS-01**: README fixes stale container names (`routing-db` -> `lpg-db`)
- [ ] **DOCS-02**: README removes manual steps now automated by db-init
- [ ] **DOCS-03**: README and DEPLOY.md fill `<REPO_URL>` placeholder
- [ ] **DOCS-04**: DEPLOY.md restructured for non-technical office employee audience

### Error Messages

- [ ] **ERR-01**: Upload errors use plain English instead of Python set notation
- [ ] **ERR-02**: Geocoding errors translated to office-friendly descriptions

### Distribution

- [ ] **DIST-01**: Build script compiles licensing module to .pyc and strips .py source for customer delivery

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Deployment Enhancements

- **DEPLOY-01**: Windows .bat shortcut on desktop for one-click daily startup
- **DEPLOY-02**: Auto-update mechanism (git pull + rebuild)
- **DEPLOY-03**: PowerShell bootstrap for fresh Windows machines (pre-WSL)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| GUI installer / Electron wrapper | Bash scripts sufficient for WSL target; GUI adds massive complexity |
| Docker Desktop instead of Docker CE | Commercial licensing implications; Docker CE in WSL is free |
| Auto-column-mapping for arbitrary CSVs | False positives assign wrong data to wrong fields |
| Column-name auto-correction | Silently masking errors is worse than clear rejection |
| MkDocs / Docusaurus documentation site | Unnecessary build step for a single-user guide |
| Obfuscation beyond .pyc | Python .pyc is sufficient deterrent; full obfuscation (PyArmor, Cython) adds build complexity |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INST-01 | Phase 13 | Pending |
| INST-02 | Phase 13 | Pending |
| INST-03 | Phase 13 | Pending |
| INST-04 | Phase 13 | Pending |
| INST-05 | Phase 13 | Pending |
| DAILY-01 | Phase 14 | Pending |
| CSV-01 | Phase 15 | Pending |
| CSV-02 | Phase 15 | Pending |
| CSV-03 | Phase 15 | Pending |
| CSV-04 | Phase 15 | Pending |
| CSV-05 | Phase 15 | Pending |
| CSV-06 | Phase 15 | Pending |
| DOCS-01 | Phase 16 | Pending |
| DOCS-02 | Phase 16 | Pending |
| DOCS-03 | Phase 16 | Pending |
| DOCS-04 | Phase 16 | Pending |
| ERR-01 | Phase 17 | Pending |
| ERR-02 | Phase 17 | Pending |
| DIST-01 | Phase 18 | Pending |

**Coverage:**
- v1.3 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-03-04*
*Last updated: 2026-03-04 after roadmap creation*
