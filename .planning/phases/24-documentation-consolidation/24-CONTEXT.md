# Phase 24: Documentation Consolidation - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Create 5 documentation artifacts so customers and developers can understand the full distribution, licensing, environment setup, and troubleshooting workflow from documentation alone -- no tribal knowledge required. Extend LICENSING.md with lifecycle stages. Add a documentation index to README.md.

</domain>

<decisions>
## Implementation Decisions

### Document placement
- Create 4 new standalone files in project root: DISTRIBUTION.md, ENV-COMPARISON.md, GOOGLE-MAPS.md, ATTRIBUTION.md
- Extend existing LICENSING.md with grace period monitoring, renewal, and 503 troubleshooting sections (don't replace -- add to existing 266-line file)
- Add a "Documentation" section to README.md listing all doc files with one-line descriptions
- All docs live in project root alongside existing docs (README.md, DEPLOY.md, GUIDE.md, etc.)

### Audience and tone
- DISTRIBUTION.md: Developer-level. Assume CLI and Docker familiarity. Exact commands, explain flags, skip preamble.
- LICENSING.md extensions: Developer-level throughout. Consistent with existing LICENSING.md style.
- ENV-COMPARISON.md: Developer-level. Comparison table format for quick reference.
- GOOGLE-MAPS.md: Plain-English for office employees. Step-by-step text with "you should see..." expected outputs. No screenshots (go stale when Google updates UI).
- ATTRIBUTION.md: Developer-level. Table + required attribution text blocks.

### Attribution scope
- Full dependency audit: scan all Python and JS dependencies for license types, not just key infrastructure
- Flag any copyleft (GPL) or restrictive licenses
- Summary table (component, license type, obligation) at top, then full required attribution text blocks below
- ATTRIBUTION.md must be bundled in tarball -- update build-dist.sh to include it in the distribution
- Key infrastructure with specific obligations: OSM data (ODbL), OSRM (BSD-2), VROOM (BSD-2), Leaflet (BSD-2), MapLibre (BSD-3), Google Maps (ToS)

### Cross-referencing
- Inline links at point of need: link where the reader needs it, e.g., "see [LICENSING.md](LICENSING.md#generating-keys)"
- No master index page beyond the README documentation section
- DISTRIBUTION.md includes exact commands inline (copy-pasteable full workflow)
- Exact commands with flag explanations, not just "run the script"

### Claude's Discretion
- Whether to add cross-references between LICENSING.md 503 troubleshooting and GOOGLE-MAPS.md (distinguishing license 503 from geocoding errors)
- Exact heading structure and section ordering within each document
- How to organize the full dependency audit (by category, alphabetical, by license type)
- Level of detail in ENV-COMPARISON.md comparison table

</decisions>

<specifics>
## Specific Ideas

- DISTRIBUTION.md should be a complete walk-through: build tarball -> generate license -> deliver to customer -> verify install. Reader can follow it end-to-end for a customer shipment.
- GOOGLE-MAPS.md follows the "Problem -> fix action" error pattern established in Phase 17 for common errors (REQUEST_DENIED, OVER_QUERY_LIMIT, INVALID_REQUEST)
- README doc index keeps descriptions to one line per doc -- don't bloat the README
- LICENSING.md extension adds sections, doesn't restructure existing content

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- LICENSING.md (266 lines): Already covers generate, activate, validate with ASCII flow diagram. Extend with lifecycle stages.
- DEPLOY.md (343 lines): Office employee audience reference for GOOGLE-MAPS.md tone
- scripts/build-dist.sh: Must be updated to include ATTRIBUTION.md in tarball
- core/licensing/: License generation and validation code -- reference for LICENSING.md lifecycle docs
- .env.example: Reference for ENV-COMPARISON.md environment variables

### Established Patterns
- All existing docs use markdown with code blocks for commands
- DEPLOY.md uses "> Who this is for" callout boxes at top
- LICENSING.md uses ASCII diagrams for flow visualization
- Error documentation follows "Problem -> fix action" pattern (Phase 17)

### Integration Points
- README.md: Add documentation index section
- scripts/build-dist.sh: Add ATTRIBUTION.md to tarball file list
- requirements.txt / package.json / package-lock.json: Source for dependency audit

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 24-documentation-consolidation*
*Context gathered: 2026-03-08*
